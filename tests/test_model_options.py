import json
import unittest
from unittest.mock import patch
from server.agent_policy import Policy
from server.discovery import probe,limit_warnings
from server.model_options import generation_options,model_config
from server.models import generate
from server.request_context import fit_context
from server.transport import Result,ServiceFailure,failure

class FlexibleModels(unittest.TestCase):
    def test_save_reload_and_wire_values(self):
        p=Policy(model="team/fine tunes:"+("v"*160),max_tokens=95000,context_window=5000001,
                 temperature=1.7,top_p=0.8,reasoning_effort="future",parameters='{"seed":42}')
        saved=Policy.model_validate_json(p.model_dump_json())
        cfg,limit,temp=model_config(saved)
        with patch("server.models.Client") as client:
            call=client.return_value.__enter__.return_value.post
            call.return_value=Result(200,b'{"choices":[{"message":{"content":"OK"}}]}')
            self.assertIn(saved.model,probe("OpenAI",saved,"fixture"))
            tested=call.call_args.kwargs["json"]
            generate(cfg,"Question",[],secret="fixture",max_tokens=limit,temperature=temp)
            chat=call.call_args.kwargs["json"]
            for key,value in {"temperature":1.7,"top_p":0.8,"seed":42,"reasoning_effort":"future",
                              "max_completion_tokens":95000,"model":p.model}.items():
                self.assertEqual(tested[key],value)
                self.assertEqual(chat[key],value)

    def test_provider_defaults_and_fallback(self):
        p=Policy(model="custom",max_tokens=None,fallback_provider="Anthropic",fallback_model="custom-b",
                 fallback_inherit=False,fallback_max_tokens=16384,fallback_reasoning_effort="high",
                 fallback_parameters={"thinking":{"type":"adaptive"}})
        self.assertEqual(generation_options(*model_config(p)),{})
        self.assertEqual(generation_options(*model_config(p,True)),{
            "max_tokens":16384,"output_config":{"effort":"high"},"thinking":{"type":"adaptive"}})
        with self.assertRaisesRegex(ServiceFailure,"requires maximum"):
            generation_options({"provider":"Anthropic"},None,None)
        self.assertEqual(generation_options({"provider":"Gemini","top_p":0,"effort":"HIGH"},None,0),
                         {"temperature":0,"topP":0,"thinkingConfig":{"thinkingLevel":"HIGH"}})

    def test_reserved_parameters_and_provider_feedback(self):
        with self.assertRaisesRegex(ServiceFailure,"messages"):
            generation_options({"provider":"OpenAI","custom":{"messages":[]}},20,None)
        error=failure(400,json.dumps({"error":{"param":"temperature","message":"maximum value is 2"}}).encode())
        self.assertIn("temperature",str(error))
        self.assertIn("2",str(error))

    def test_large_input_and_model_metadata(self):
        body="A"*60000
        self.assertEqual(json.loads(fit_context("new",body,[],[],"",95000))["request"],body)
        with patch("server.discovery.Client") as client:
            client.return_value.__enter__.return_value.get.return_value=Result(200,b'{"outputTokenLimit":8000}')
            warnings=limit_warnings({"provider":"Gemini","model":"new","context_window":0},95000,"fixture")
            self.assertIn("8000",warnings[0])

    def test_probe_accepts_and_rejects_custom_fields_over_http(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from threading import Thread
        from server.transport import Client
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if "unknown_option" in request:
                    code,body=400,{"error":{"param":"unknown_option","message":"Unknown parameter"}}
                else:
                    code,body=200,{"choices":[{"message":{"content":"OK"}}]}
                self.send_response(code)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())
        http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        worker=Thread(target=http.serve_forever,daemon=True)
        worker.start()
        try:
            post=Client.post
            url=f"http://127.0.0.1:{http.server_port}/chat/completions"
            def local(client,remote,**kwargs):return post(client,url,**kwargs)
            with patch.object(Client,"post",local):
                self.assertIn("custom",probe("OpenAI",Policy(model="custom",max_tokens=None),"fixture"))
                with self.assertRaisesRegex(ServiceFailure,"unknown_option"):
                    probe("OpenAI",Policy(model="custom",parameters={"unknown_option":1}),"fixture")
        finally:
            http.shutdown()
            http.server_close()
            worker.join()

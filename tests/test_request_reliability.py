import json
import unittest
from unittest.mock import patch
from server.conversation import plan_turn
from server.models import generate
from server.request_context import fit_context
from server.transport import failure,ServiceFailure,retry_delay

class ReliabilityTests(unittest.TestCase):
    def test_twenty_five_followups_under_multibyte_pressure(self):
        history=[]
        rows=[dict(id=str(i),body="文"*3000,state="approved") for i in range(12)]
        def stream(client,url,headers,payload):
            question=json.loads(payload["messages"][-1]["content"])
            self.assertTrue(question["request"].startswith("Review milestone"))
            self.assertLess(len(payload["messages"][-1]["content"].encode()),48000)
            self.assertTrue(question["excerpts"])
            yield {"choices":[{"delta":{"content":"Reviewed."},"finish_reason":"stop"}]}
        with patch("server.models.Client.events",stream):
            for i in range(25):
                prompt=f"Review milestone {i}"
                answer,_,_=generate({"provider":"OpenAI","model":"gpt-4o","question":prompt,"context_window":48000},prompt+"\n"+"notes "*8000,rows,history,secret="fixture",emit=lambda _:None)
                self.assertEqual(answer,"Reviewed.")
                history += [dict(role="user",body=prompt),dict(role="assistant",body="点"*1000)]
    def test_limits_preserve_question_or_explicitly_fail(self):
        with self.assertRaises(ServiceFailure):
            fit_context("custom","文"*3000,[],[],"",2000,window_override=1900)
        content=fit_context("custom","Hi",[],[],"",100,window_override=1024)
        self.assertEqual(json.loads(content)["request"],"Hi")
    def test_retry_headers_and_sanitization(self):
        limited=failure(429,b'{"error":{"code":"rate_limit_exceeded","message":"private content"}}',{"Retry-After":"7","X-Request-ID":"req-001"})
        self.assertEqual((limited.transient,limited.retry_after,limited.request_id),(True,7,"req-001"))
        self.assertNotIn("private",str(limited))
        for status,reason in [(429,"insufficient_quota"),(401,"bad key"),(400,"context_length_exceeded"),(400,"invalid model")]:
            self.assertFalse(failure(status,json.dumps({"error":reason}).encode()).transient)
    def test_retry_boundary(self):
        exc=failure(503)
        self.assertIsNotNone(retry_delay(exc,0,False,False))
        for args in [(1,False,False),(0,True,False),(0,False,True)]:
            self.assertIsNone(retry_delay(exc,*args))
        for exc in [failure(429,headers={"Retry-After":"8"}),failure(401),failure(400)]:
            self.assertIsNone(retry_delay(exc,0,False,False))
        self.assertEqual(retry_delay(failure(429,headers={"Retry-After":"2"}),0,False,False),2)

    def test_cutoff_never_finishes_as_success(self):
        event={"choices":[{"delta":{"content":"half"},"finish_reason":"length"}]}
        with patch("server.models.Client.events",return_value=iter([event])),self.assertRaisesRegex(ServiceFailure,"output limit"):
            generate({"provider":"OpenAI","model":"fixture"},"q",[],secret="fixture",emit=lambda _:None)
    def test_common_queries_use_one_generation_call(self):
        def unexpected(*args,**kwargs):self.fail("extra classification call")
        for question,kind in [("What is Jira?","general"),("What is our next milestone?","project")]:
            self.assertEqual(plan_turn(unexpected,"u","p",question,[]).kind,kind)

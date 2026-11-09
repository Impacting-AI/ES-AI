import unittest
from unittest.mock import Mock
from server.chat_sources import chat_evidence,cited_sources,clean_text,public_messages,VisibleStream
from server.conversation import plan_turn
from server.knowledge import select_context,process

class ChatSourceTests(unittest.TestCase):
    source="0befb4d2-3a2d-4df0-a74c-21afcba41034"

    def test_source_aliases_and_citations(self):
        refs=[dict(id=self.source+".1",sid=self.source,title="Approved scope",location="Page 4",body="Quantities",state="approved")]
        aliases=chat_evidence(refs)
        self.assertNotIn(self.source,str(aliases))
        self.assertEqual(aliases[0]["id"],"S1")
        raw="Quantities come from the model [S1, S99]."
        self.assertEqual(cited_sources(raw,refs,["S1"]),refs)
        self.assertEqual(cited_sources(raw,refs,[]),[])
        self.assertEqual(clean_text(raw),"Quantities come from the model.")
        old={"role":"assistant","body":f"Reviewed [{self.source}.1].","citations":refs}
        self.assertEqual(public_messages([old])[0]["body"],"Reviewed.")

    def test_stream_split_at_every_character(self):
        raw=f"Review quantities [S1, S2]. Next [{self.source}.1]. See [the scope](https://example.com)."
        for width in range(1,len(raw)+1):
            chunks=[]
            writer=VisibleStream(chunks.append)
            for i in range(0,len(raw),width):writer.write(raw[i:i+width])
            writer.finish()
            output="".join(chunks)
            self.assertEqual(output,clean_text(raw))
            self.assertNotIn("S1",output)
            self.assertNotIn("S2",output)
            self.assertNotIn(self.source,output)
            self.assertIn("[the scope](https://example.com)",output)

    def test_overview_and_follow_up(self):
        ask=Mock()
        intent=plan_turn(ask,"u","p","What knowledge do you have about this project?",[])
        self.assertEqual(intent.kind,"overview")
        self.assertIn("documents",intent.sources)
        self.assertEqual(plan_turn(ask,"u","p","Why?",[dict(role="assistant",body="Start with import.")]).kind,"conversation")
        ask.assert_not_called()

    def test_long_scope_includes_later_stages(self):
        content="Project purpose: Review quantities.\n"+("Review requirements.\n"*2500)+"\nMilestone 3: Handover and acceptance."
        state,_,parts=process("Approved scope.txt",content.encode())
        self.assertEqual(state,"Ready")
        rows=[dict(id=str(i),sid="scope",title="Approved scope",state="approved",position=i,location=loc,body=body) for i,(loc,body) in enumerate(parts)]
        chosen=select_context(rows,"project purpose scope",[],6,breadth=True)
        self.assertTrue(any("Project purpose" in r["body"] for r in chosen))
        self.assertTrue(any("Milestone 3:" in r["body"] for r in chosen))

    def test_repository_scope_through_all_provider_adapters(self):
        from pathlib import Path
        import json
        from unittest.mock import patch
        from server.models import generate
        from server.response_style import chat_style
        from server.transport import Result
        document=Path(__file__).resolve().parents[1]/"REQUIREMENTS.md"
        if not document.is_file():self.skipTest("Repository requirements document is unavailable in this installation")
        raw=document.read_bytes()
        status,_,parts=process("Project requirements.md",raw)
        self.assertEqual(status,"Ready")
        refs=select_context([dict(id=f"{self.source}.{i}",sid=self.source,title="PM AI ES requirements",
                                  state="approved",position=i,location=loc,body=body)
                             for i,(loc,body) in enumerate(parts)],"purpose milestones",[],8,breadth=True)
        for provider in ("OpenAI","Anthropic","Gemini"):
            text="PM AI ES helps the team plan and supervise project work [S1]."
            responses={"OpenAI":{"choices":[{"message":{"content":text}}]},
                       "Anthropic":{"content":[{"text":text}]},
                       "Gemini":{"candidates":[{"content":{"parts":[{"text":text}]}}]}}
            with patch("server.models.Client") as client:
                post=client.return_value.__enter__.return_value.post
                post.return_value=Result(200,json.dumps(responses[provider]).encode())
                info={}
                answer,_,_=generate(dict(provider=provider,model="fixture"),"What do you know about this project?",
                                    chat_evidence(refs),secret="fixture",instructions=chat_style("Balanced"),diagnostics=info)
                self.assertNotIn(self.source,json.dumps(post.call_args.kwargs["json"]))
                self.assertEqual(clean_text(answer),"PM AI ES helps the team plan and supervise project work.")
                self.assertEqual(cited_sources(answer,refs,info["used_ids"])[0]["sid"],self.source)

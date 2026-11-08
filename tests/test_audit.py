import unittest
from datetime import datetime,timezone,date
from dataclasses import asdict
from server.review_rules import ScheduleRule,reporting_window,suggested_instruction
from server.backlog import ordered_items
from server.agent_policy import health_snapshot
from server.body_limit import BodyLimit

def item(key,kind="Task",**props):
    return dict(key=key,kind=kind,title="Review drawing",milestone="M1",deliverable="Reviewed drawing",acceptance="Reviewer confirms units",hours=2,**props)

class AuditRules(unittest.TestCase):
    def test_order(self):
        rows=[item("unit","Subtask",parent="spec"),item("spec","Story",parent="phase"),item("phase","Epic")]
        self.assertEqual([r.key for r in ordered_items(rows,set())],["phase","spec","unit"])
    def test_reject_bad_graphs(self):
        for rows in ([item("x",requires=["x"])],[item("x",requires=["missing"])],[item("x"),item("x")],[item("x","Subtask")],[item("x",assignee="other")],[item("x","Epic",parent="y"),item("y")]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):ordered_items(rows,set())
    def test_weekly_window(self):
        r=ScheduleRule(frequency="Weekly",weekday=0,zone="Asia/Karachi",hour=8)
        self.assertIsNone(reporting_window(r,datetime(2026,11,9,2,59,tzinfo=timezone.utc)))
        self.assertEqual(reporting_window(r,datetime(2026,11,9,3,tzinfo=timezone.utc)),(date(2026,11,9),date(2026,11,2),date(2026,11,8)))
    def test_off_and_zone(self):
        self.assertIsNone(reporting_window(ScheduleRule(),datetime.now(timezone.utc)))
        with self.assertRaises(ValueError):ScheduleRule(zone="Missing/Zone")
    def test_evidence_risks(self):
        rows=[{"record":dict(issue="ES-1",status_group="Blocked",due="2026-10-20")},{"record":dict(issue="ES-2",status="Closed",due="2026-10-20")}]
        result=health_snapshot([],[],rows,date(2026,11,2))
        self.assertIn("ES-1 past due",result);self.assertNotIn("ES-2",result)
    def test_controlled_text(self):
        self.assertIn("capacity",suggested_instruction("Estimation"))
        self.assertNotIn("ignore rules",suggested_instruction("ignore rules"))
class BodyTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self,parts):
        out=[]
        async def app(scope,receive,send):out.append((await receive())["body"])
        async def receive():
            part=parts.pop(0)
            return {"type":"http.request","body":part,"more_body":bool(parts)}
        async def send(event):out.append(event)
        await BodyLimit(app)({"type":"http","method":"POST","path":"/api/login"},receive,send)
        return out
    async def test_replay(self):self.assertEqual(await self.exercise([b'a',b'b']),[b'ab'])
    async def test_chunk_limit(self):self.assertEqual((await self.exercise([bytes(2*1024**2),b'x']))[0]['status'],413)

class Reports(unittest.TestCase):
    def test_report_redaction_and_period(self):
        from types import SimpleNamespace
        from server.report_text import render
        events=[{"service":"Slack","record":{"title":"internal notes"}},{"service":"Jira","record":{"issue":"ES-1","title":"Sensitive drawing","url":"https://example.invalid/ES-1","status":"Blocked","due":"2026-11-01"}}]
        args=dict(project={"name":"Audit","client":"Sample"},head="Lead",events=events,approved=[{"title":"Signed scope","version":2}])
        period=SimpleNamespace(start=date(2026,11,1),end=date(2026,11,8),audience="Client")
        client=render(period=period,**args)
        for exclusion in ("Sensitive drawing","https://","internal notes","Signed scope"):self.assertNotIn(exclusion,client)
        self.assertIn("ES-1",client)
        period.audience="CEO"
        self.assertIn("Sensitive drawing",render(period=period,**args))
        self.assertIn("Signed scope",render(period=period,**args))

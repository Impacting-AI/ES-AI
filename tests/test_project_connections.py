import hashlib
import hmac
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from server.activity_feed import read_page
from server.discovery import verify_binding
from server.project_links import store_mapping
from server.provider_hooks import authenticated, destination
from server.transport import ServiceFailure
from tests.test_connections import reply


class FixtureDatabase:
    def __init__(self):
        self.db=sqlite3.connect(":memory:")
        self.db.row_factory=sqlite3.Row
        self.db.create_function("new_id",0,lambda:str(uuid4()))
        self.db.create_function("now",0,lambda:"2026-01-01")
        self.db.executescript("""CREATE TABLE project_links(pid,service,workspace,destination,external_id,resource_name,resource_url,
            board_id,verified_at,updated_at,queued,poll_after,mapping_id DEFAULT(new_id()),PRIMARY KEY(pid,service),UNIQUE(service,workspace,destination));
            CREATE TABLE delivery_events(pid,service,mapping_id,remote_id);
            CREATE TABLE agent_settings(agent_id,policy);
            INSERT INTO agent_settings VALUES ('pm-ai-es','{"jira_site":"site","slack_team":"team"}');""")
        schema=(Path(__file__).parents[1]/"server/schema.sql").read_text()
        view=schema.split("CREATE OR REPLACE VIEW mapped_delivery_events AS")[1].split(";")[0]
        self.db.execute("CREATE VIEW mapped_delivery_events AS "+view.replace("::boolean",""))

    def execute(self,sql,args=()):
        return self.db.execute(sql.replace("%s","?").replace(" FOR UPDATE",""),args)


class ProjectConnectionTests(unittest.TestCase):
    def test_mapping_isolation_replace_disconnect_and_reconnect(self):
        db=FixtureDatabase()
        def link(pid,service,key,expected=None):
            store_mapping(db,pid,service,"team" if service=="Slack" else "site",dict(destination=key,external_id=key,resource_name=key,resource_url="url"),expected=expected)
            return db.execute("SELECT mapping_id FROM project_links WHERE pid=? AND service=?",(pid,service)).fetchone()[0]
        def visible(pid):
            return sorted(r[0] for r in db.execute("SELECT remote_id FROM mapped_delivery_events WHERE pid=?",(pid,)))
        for pid,jira,slack in [("a","FDX","CA"),("b","FFG","CB")]:
            for service,target in [("Jira",jira),("Slack",slack)]:
                identity=link(pid,service,target)
                db.execute("INSERT INTO delivery_events VALUES (?,?,?,?)",(pid,service,identity,target))
        self.assertEqual(visible("a"),["CA","FDX"])
        self.assertEqual(visible("b"),["CB","FFG"])
        with self.assertRaises(ServiceFailure):link("a","Slack","CB")
        with self.assertRaises(ServiceFailure):link("a","Jira","NEW","stale")
        link("a","Jira","NEW")
        self.assertEqual(visible("a"),["CA"])
        db.execute("DELETE FROM project_links WHERE pid='a' AND service='Slack'")
        link("a","Slack","CA")
        self.assertEqual(visible("a"),[])
        db.execute("UPDATE project_links SET verified_at=NULL WHERE pid='b' AND service='Jira'")
        self.assertEqual(visible("b"),["CB"])

    @patch("server.discovery.Client")
    def test_numeric_jira_id_requires_browse(self,client):
        c=client.return_value.__enter__.return_value
        p=SimpleNamespace(jira_site="https://fixture.atlassian.net",jira_email="user")
        for allowed in [True,False]:
            c.get.side_effect=[reply({"key":"FDX","name":"FacadeX","id":"123"}),reply({"permissions":{"BROWSE_PROJECTS":{"havePermission":allowed}}})]
            if allowed:self.assertEqual(verify_binding("Jira","123",p,"key")["destination"],"FDX")
            else:
                with self.assertRaises(ServiceFailure):verify_binding("Jira","123",p,"key")
        with self.assertRaises(ServiceFailure):verify_binding("Slack","123",p,"key")

    def test_threads_preserve_channel_and_cursor(self):
        c=MagicMock()
        c.post.return_value=reply({"ok":True,"team_id":"T1"})
        c.get.side_effect=[reply({"messages":[{"ts":"100.1","reply_count":1}]}),reply({"messages":[{"ts":"101.1","thread_ts":"100.1","text":"blocked"}]})]
        link=dict(destination="C1",last_sync=None,scan_cursor="")
        args=(c,"Slack",link,SimpleNamespace(slack_team="T1"),"key",datetime.now(timezone.utc),True)
        events,link["scan_cursor"]=read_page(*args)
        self.assertTrue(link["scan_cursor"])
        events,cursor=read_page(*args)
        self.assertFalse(cursor)
        self.assertEqual(events[0][2]["title"],"blocked")
        self.assertEqual(c.get.call_args.kwargs["params"]["channel"],"C1")

    def test_signed_webhooks_bind_body_and_source(self):
        data={"team_id":"T1","event":{"channel":"C1","subtype":"message_deleted"}}
        body=json.dumps(data).encode()
        for provider in ["Slack","Jira"]:
            slack=provider=="Slack"
            sig=hmac.new(b"key",b"v0:123:"+body if slack else body,hashlib.sha256).hexdigest()
            headers={"x-slack-request-timestamp":"123","x-slack-signature":"v0="+sig} if slack else {"x-hub-signature":"sha256="+sig}
            self.assertTrue(authenticated(provider,"key",headers,body,123))
            self.assertFalse(authenticated(provider,"key",headers,body+b"x",123))
            if slack:self.assertFalse(authenticated(provider,"key",headers,body,999))
        self.assertEqual(destination("Slack",data),("T1","C1",True))

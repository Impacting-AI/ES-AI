import json
import unittest
from unittest.mock import patch
from server.agent_policy import Policy
from server.discovery import probe, fingerprint, options, jira_preflight, model_list
from server.transport import Result, ServiceFailure, failure
from server.connectors import ExternalAction, publish

def reply(data,code=200,headers=None):
    return Result(code,json.dumps(data).encode(),headers)


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.p=Policy(model="model-a",jira_site="https://fixture.atlassian.net",jira_email="admin@example.test",slack_team="TFIXTURE")

    @patch("server.discovery.generate")
    def test_selected_model_generates_text(self,generate):
        generate.return_value=("OK",8,1)
        self.assertIn("model-a",probe("OpenAI",self.p,"test-key"))
        self.assertEqual(generate.call_args.args[0]["model"],"model-a")
        self.assertEqual(generate.call_args.kwargs["max_tokens"],self.p.max_tokens)
        self.assertEqual(generate.call_args.kwargs["secret"],"test-key")

    @patch("server.discovery.generate")
    def test_empty_answer_is_not_verified(self,generate):
        generate.return_value=("",8,0)
        with self.assertRaises(ServiceFailure):probe("OpenAI",self.p,"test-key")

    @patch("server.discovery.generate")
    def test_fallback_same_service_probed(self,generate):
        generate.return_value=("OK",8,1)
        probe("OpenAI",self.p.model_copy(update={"fallback_provider":"OpenAI","fallback_model":"model-b"}),"test-key")
        self.assertEqual([c.args[0]["model"] for c in generate.call_args_list],["model-a","model-b"])

    def test_failure_classification_is_redacted(self):
        for code,reason,expected in [(401,"fixture-secret","Invalid credentials"),(403,"forbidden","Insufficient permissions"),(404,"model_not_found","Requested model or resource unavailable"),(429,"insufficient_quota","Quota or billing limit reached"),(429,"too_many_requests","Service rate limit reached"),(503,"offline","Network or service error")]:
            with self.subTest(code=code,reason=reason):
                e=failure(code,json.dumps({"error":{"code":reason,"message":"fixture-secret"}}).encode())
                self.assertEqual(e.category,expected)
                self.assertNotIn("fixture-secret",str(e))

    def test_fingerprint_binds_real_parameters(self):
        f=lambda p,k:fingerprint("signing","OpenAI",p,k)
        self.assertNotEqual(f(self.p,"one"),f(self.p,"two"))
        self.assertNotEqual(f(self.p,"one"),f(self.p.model_copy(update={"model":"other"}),"one"))
        self.assertNotEqual(f(self.p,"one"),f(self.p.model_copy(update={"temperature":0.3}),"one"))
        self.assertEqual(f(self.p,"one"),f(self.p.model_copy(update={"name":"Updated name"}),"one"))

    @patch("server.discovery.Client")
    def test_jira_options_page(self,C):
        c=C.return_value.__enter__.return_value
        c.get.return_value=reply({"total":2,"values":[{"key":"ONE","name":"One"}]})
        page=options("Jira","projects",self.p,"fake")
        self.assertEqual(page["items"][0]["id"],"ONE")
        self.assertEqual(page["next"],"1")
        self.assertTrue(c.get.call_args.args[0].endswith("/project/search"))
        self.assertEqual(c.get.call_args.kwargs["auth"],(self.p.jira_email,"fake"))

    @patch("server.discovery.Client")
    def test_slack_credential_scope_failure(self,C):
        c=C.return_value.__enter__.return_value
        c.post.return_value=reply({"ok":True,"team_id":"TFIXTURE"})
        c.get.return_value=reply({"ok":False,"error":"missing_scope"})
        with self.assertRaisesRegex(ServiceFailure,"permissions"):options("Slack","channels",self.p,"fake")

    @patch("server.discovery.Client")
    def test_workspace_mismatch_stops_discovery(self,C):
        c=C.return_value.__enter__.return_value;c.post.return_value=reply({"ok":True,"team_id":"TOTHER"})
        with self.assertRaises(ServiceFailure):options("Slack","users",self.p,"fake")
        c.get.assert_not_called()

    @patch("server.discovery.options")
    def test_subtask_requires_parent(self,load):
        load.side_effect=[{"items":[{"id":"CREATE_ISSUES","allowed":True}]},{"items":[{"id":"17","name":"Subtask","subtask":True}],"next":""}]
        a=ExternalAction(kind="Jira issue",destination="ONE",title="Test",reference="Subtask")
        with self.assertRaisesRegex(ServiceFailure,"parent"):jira_preflight(a,self.p,"fake")

    @patch("server.connectors.Client")
    def test_approved_notification_endpoint(self,C):
        c=C.return_value.__enter__.return_value
        c.post.side_effect=[reply({"ok":True,"team_id":"TFIXTURE"}),reply({"ok":True,"ts":"1.2"})]
        a=ExternalAction(kind="Slack Jira update",destination="CABC",title="Issue reviewed",reference="ABC-1")
        self.assertEqual(publish(a,self.p.model_copy(update={"slack_notifications":True}),"fake","approval-id"),"1.2")
        self.assertEqual(c.post.call_args.kwargs["json"]["channel"],"CABC")

    @patch("server.discovery.Client")
    def test_model_listing_is_separate_from_probe(self,C):
        c=C.return_value.__enter__.return_value;c.get.return_value=reply({"data":[{"id":"z"},{"id":"a"}]})
        self.assertEqual(model_list("OpenAI","fake"),["a","z"])
        c.post.assert_not_called()

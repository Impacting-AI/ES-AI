import unittest
from unittest.mock import patch
import json
from pydantic import ValidationError
from server.agent_policy import Policy,choose_tool,permitted,health_snapshot,reserve_estimate
from server.models import generate
from server.connectors import ExternalAction,publish
from server.transport import Result


class AgentTests(unittest.TestCase):
    def test_all_modes_enforce_pause(self):
        for tool in ['answer','plan','health']:
            with self.assertRaises(ValueError):permitted(Policy(enabled=False),tool)

    def test_analyse_and_draft(self):
        with self.assertRaises(ValueError):permitted(Policy(mode='Analyse'),'plan')
        permitted(Policy(mode='Draft'),'plan')

    def test_tools_off(self):
        for tool,flag in [('answer','allow_chat'),('plan','allow_plan'),('health','allow_health')]:
            with self.assertRaises(ValueError):permitted(Policy(**{flag:False}),tool)

    def test_invalid_config(self):
        for bad in [{'jira_site':'https://example.org'},{'timezone':'bad-zone'},{'max_tokens':99999},{'slack_team':'abc'}]:
            with self.assertRaises(ValidationError):Policy(**bad)

    def test_router(self):
        self.assertEqual(choose_tool('Draft a project plan'),'plan')
        self.assertEqual(choose_tool('Check project health'),'health')
        self.assertEqual(choose_tool('What plan did the client approve?'),'answer')

    def test_budget(self):
        with self.assertRaises(ValueError):reserve_estimate(Policy(monthly_budget=1),1000)
        p=Policy(input_rate=2,output_rate=6,max_tokens=1000)
        self.assertAlmostEqual(reserve_estimate(p,1488),.010)

    def test_health(self):
        self.assertIn('Plans awaiting approval: 1',health_snapshot([{'state':'draft'}],[{'state':'draft'}]))
        self.assertIn('Approve a scope',health_snapshot([],[]))

    def test_unmapped_destinations(self):
        for kind,dest,ref in [('Jira project','two spaces','lead'),('Slack invitation','wrong','U123'),('Email report','two@x.com,one@x.com','')]:
            with self.assertRaises(ValidationError):ExternalAction(kind=kind,title='Example',destination=dest,reference=ref)

    @patch('server.models.Client')
    def test_all_model_adapters(self,client):
        replies={
            'OpenAI':{'choices':[{'message':{'content':'example'}}],'usage':{'prompt_tokens':2,'completion_tokens':3}},
            'Anthropic':{'content':[{'text':'example'}],'usage':{'input_tokens':2,'output_tokens':3}},
            'Gemini':{'candidates':[{'content':{'parts':[{'text':'example'}]}}],'usageMetadata':{'promptTokenCount':2,'totalTokenCount':5}}
        }
        post=client.return_value.__enter__.return_value.post
        for provider,reply in replies.items():
            post.return_value=Result(200,json.dumps(reply).encode())
            self.assertEqual(generate({'provider':provider,'model':'test'},'Question',[],secret='fixture',max_tokens=512,instructions='Be brief'),('example',2,3))
            payload=post.call_args.kwargs['json']
            self.assertIn('512',str(payload))
            self.assertIn('Be brief',str(payload))

    @patch('server.connectors.Client')
    def test_jira_issue_fields(self,client):
        c=client.return_value.__enter__.return_value
        c.post.return_value=Result(201,b'{"key":"PROJ-17"}')
        a=ExternalAction(kind='Jira issue',destination='PROJ',title='Review scope',body='Verify deliverables',reference='Task',assignee='staff-id',due='2026-11-20')
        remote=publish(a,Policy(jira_site='https://example.atlassian.net',jira_email='test@example.com'),'fixture','action-id')
        self.assertEqual(remote,'PROJ-17')
        fields=c.post.call_args.kwargs['json']['fields']
        self.assertEqual(fields['assignee']['accountId'],'staff-id')
        self.assertEqual(fields['duedate'],'2026-11-20')

    @patch('server.connectors.Client')
    def test_slack_workspace_guard(self,client):
        c=client.return_value.__enter__.return_value
        c.post.return_value=Result(200,b'{"ok":true,"team_id":"TOTHER"}')
        with self.assertRaises(ValueError):publish(ExternalAction(kind='Slack channel',destination='project-test',title='Test'),Policy(slack_team='TEXPECTED'),'fixture','id')
        self.assertEqual(c.post.call_count,1)

    @patch('server.connectors.Client')
    def test_email_idempotency(self,client):
        c=client.return_value.__enter__.return_value
        c.post.return_value=Result(200,b'{"id":"receipt"}')
        self.assertEqual(publish(ExternalAction(kind='Email report',destination='pm@example.com',title='Review',body='Report'),Policy(email_sender='reports@example.com'),'fixture','unique-01'),'receipt')
        self.assertEqual(c.post.call_args.kwargs['headers']['Idempotency-Key'],'unique-01')

class AccessAndImportTests(unittest.TestCase):
    def test_roles(self):
        from server.agent_policy import may_admin,may_edit
        self.assertTrue(may_admin('CEO'))
        self.assertFalse(may_admin('Project Manager'))
        self.assertTrue(may_edit('Project Manager'))
        self.assertFalse(may_edit('Read-Only'))

    def test_import_provenance(self):
        from server.imports import parse_export
        raw=json.dumps({'platform':'Slack','messages':[{'sender':'A','text':'Earlier','timestamp':'2026-11-01T09:00:00Z'},{'sender':'B','text':'Later','attachments':['drawing.pdf']}]}).encode()
        platform,body,digest=parse_export(raw)
        self.assertEqual(platform,'Slack')
        self.assertLess(body.index('Earlier'),body.index('Later'))
        self.assertIn('2026-11-01T09:00:00Z | A',body)
        self.assertIn('drawing.pdf',body)
        self.assertEqual(digest,parse_export(raw)[2])

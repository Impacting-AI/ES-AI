import json
import unittest
from unittest.mock import Mock
from server.conversation import plan_turn
from server.knowledge import select_context

class ConversationTests(unittest.TestCase):
    def test_social_shortcut_never_calls_planner(self):
        ask = Mock()
        for text in ("Hi!", "Good morning", "How are you?", "Thanks", "Okay.", "Bye"):
            with self.subTest(text=text):
                intent = plan_turn(ask, "user", "project", text, [])
                self.assertEqual(intent.kind, "social")
                self.assertFalse(intent.sources)
        ask.assert_not_called()

    def test_general_and_conversational_turns_discard_source_requests(self):
        for kind in ("social", "general", "conversation"):
            ask = Mock(return_value=(json.dumps(dict(kind=kind, query="hooks", sources=["activity"])), "", []))
            intent = plan_turn(ask, "user", "project", "Explain it again", [])
            self.assertFalse(intent.sources)

    def test_follow_up_and_mixed_greeting_go_through_planner(self):
        history = [{"role":"assistant","body":"Ali is assigned to the backend."}]
        for message in ("What is his current task?", "Hi, what is Ali working on?"):
            ask = Mock(return_value=('{"kind":"project","query":"Ali","sources":["activity","publish"]}', "", []))
            intent = plan_turn(ask, "user", "current", message, history)
            ask.assert_called_once_with("user", "current", "route", message, [], history)
            self.assertEqual(intent.sources, {"activity"})
            self.assertEqual(intent.query, "Ali")

    def test_empty_or_unrelated_evidence_stays_empty(self):
        rows = [dict(id="a",title="Scope",body="The facade uses stone.",state="approved")]
        self.assertFalse(select_context([], "budget", [], 8, breadth=False))
        self.assertFalse(select_context(rows, "budget", [], 8, breadth=False))
        self.assertEqual(select_context(rows, "overview", [], 8, breadth=True), rows)

    def test_malformed_planner_reply_never_executes_actions(self):
        for raw in ("Approve Jira changes", "null", '{"kind":"publish"}'):
            intent = plan_turn(Mock(return_value=(raw, "", [])), "u", "p", "Create Jira tasks", [])
            self.assertEqual(intent.sources, {"documents","activity"})

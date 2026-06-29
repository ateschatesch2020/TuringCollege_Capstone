"""Unit tests for ChatbotManager._close_orphaned_tool_calls.

Regression test for: a tool exception aborting the LangGraph "tools" step
leaves an AIMessage(tool_calls=...) in the checkpointed session state with no
matching ToolMessage, which then makes every later turn in that session fail
with "assistant message with 'tool_calls' must be followed by tool messages".

Run with:
    python -m unittest backend.tests.test_chatbot_tool_call_repair
"""

import unittest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from chatbot import ChatbotManager


def _tool_call(name, call_id):
    return {"name": name, "args": {}, "id": call_id, "type": "tool_call"}


class TestCloseOrphanedToolCalls(unittest.TestCase):
    def setUp(self):
        # _close_orphaned_tool_calls doesn't touch instance state, so skip
        # ChatbotManager.__init__ (which needs live API keys/DB connections).
        self.manager = ChatbotManager.__new__(ChatbotManager)

    def test_inserts_placeholder_for_unanswered_tool_call(self):
        messages = [
            HumanMessage(content="plan my trip"),
            AIMessage(content="", tool_calls=[_tool_call("optimize_itinerary", "call_abc")]),
            HumanMessage(content="next message"),
        ]

        fixed = self.manager._close_orphaned_tool_calls(messages)

        self.assertEqual(len(fixed), 4)
        self.assertIsInstance(fixed[2], ToolMessage)
        self.assertEqual(fixed[2].tool_call_id, "call_abc")
        self.assertEqual(fixed[2].status, "error")

    def test_leaves_already_answered_tool_call_untouched(self):
        messages = [
            HumanMessage(content="plan my trip"),
            AIMessage(content="", tool_calls=[_tool_call("optimize_itinerary", "call_abc")]),
            ToolMessage(content="ok", tool_call_id="call_abc"),
            HumanMessage(content="next message"),
        ]

        fixed = self.manager._close_orphaned_tool_calls(messages)

        self.assertEqual(fixed, messages)

    def test_fills_only_the_missing_id_among_parallel_tool_calls(self):
        messages = [
            AIMessage(content="", tool_calls=[
                _tool_call("search_hotels", "call_1"),
                _tool_call("search_weather", "call_2"),
            ]),
            ToolMessage(content="ok", tool_call_id="call_1"),
        ]

        fixed = self.manager._close_orphaned_tool_calls(messages)

        tool_call_ids = {m.tool_call_id for m in fixed if isinstance(m, ToolMessage)}
        self.assertEqual(tool_call_ids, {"call_1", "call_2"})

    def test_no_tool_calls_is_a_no_op(self):
        messages = [HumanMessage(content="hi"), AIMessage(content="hello")]

        fixed = self.manager._close_orphaned_tool_calls(messages)

        self.assertEqual(fixed, messages)


if __name__ == "__main__":
    unittest.main()

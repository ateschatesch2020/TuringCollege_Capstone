"""Unit tests for ChatbotManager.chat()/chat_stream() (Phase 5 of the backend refactor):

- chat() previously returned the evaluator's internal feedback commentary instead of
  the assistant's real answer, because the evaluator node appends its own message
  after the worker's answer and chat() blindly took result["messages"][-1]. Verified
  empirically before this fix: with a mocked worker returning "the real answer",
  chat() returned "Evaluator Feedback on this answer: ..." instead. Fixed by tagging
  the evaluator's synthetic message (name="evaluator" in agent.py) and having chat()
  skip it via chatbot._last_answer_content().
- chat() and chat_stream() were ~90% duplicated (state construction + history
  persistence); both now go through shared chatbot._build_initial_state()/
  _build_config()/_persist_turn(). This asserts they persist equivalent history for
  the same input.

Run with:
    pytest backend/tests/test_chatbot_chat_methods.py
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver

from agent import AgentGraph
from chatbot import ChatbotManager


def _mocked_bundle(worker_response="the real answer", success=True):
    # A bare MagicMock().invoke() doesn't participate in LangChain's callback/streaming
    # system, so chat_stream()'s AIMessageChunk accumulation sees nothing from it --
    # FakeListChatModel is a real Runnable and streams properly under LangGraph's
    # stream_mode="messages", matching how a real ChatOpenRouter model behaves.
    worker_llm = FakeListChatModel(responses=[worker_response])
    evaluator_llm = MagicMock()
    evaluator_llm.invoke.return_value = MagicMock(
        feedback="looks complete", success_criteria_met=success, user_input_needed=False,
    )
    return {
        "model": MagicMock(),
        "worker_llm_with_tools": worker_llm,
        "evaluator_llm_with_output": evaluator_llm,
    }


def _build_manager(db_path: str) -> ChatbotManager:
    """A minimal ChatbotManager wired to a real AgentGraph with a mocked LLM bundle --
    skips __init__ (which needs live API keys, embedding models, and the real
    test_history.db) the same way test_chatbot_tool_call_repair.py does."""
    manager = ChatbotManager.__new__(ChatbotManager)
    manager.connection_string = f"sqlite:///{db_path}"
    bundle = _mocked_bundle()
    manager._agent_graph = AgentGraph(get_bundle=lambda model_id: bundle, tools=[], checkpointer=MemorySaver())
    manager.graph = manager._agent_graph.graph
    return manager


class _TempDbTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except PermissionError:
            pass  # Windows sometimes briefly holds the sqlite file handle open


class TestChatReturnsRealAnswer(_TempDbTestCase):
    def test_chat_returns_worker_answer_not_evaluator_feedback(self):
        manager = _build_manager(self.db_path)

        response = manager.chat("session-a", "hello")

        self.assertEqual(response, "the real answer")
        self.assertNotIn("Evaluator Feedback", response)


class TestChatAndChatStreamPersistEquivalentHistory(_TempDbTestCase):
    def test_both_entry_points_persist_one_user_and_one_ai_message(self):
        manager_a = _build_manager(self.db_path)
        manager_a.chat("session-a", "hello")

        manager_b = _build_manager(self.db_path)
        "".join(manager_b.chat_stream("session-b", "hello"))  # drain the generator

        history_a = manager_a._get_session_history("session-a").messages
        history_b = manager_b._get_session_history("session-b").messages

        self.assertEqual(len(history_a), 2)
        self.assertEqual(len(history_b), 2)
        self.assertEqual(history_a[0].content, "hello")
        self.assertEqual(history_b[0].content, "hello")
        self.assertEqual(history_a[1].content, "the real answer")
        self.assertEqual(history_b[1].content, "the real answer")


if __name__ == "__main__":
    unittest.main(verbosity=2)

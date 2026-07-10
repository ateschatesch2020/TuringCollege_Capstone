"""Unit tests for ChatbotManager's LangGraph time-travel support
(_find_turn_start / retry_stream):

- _find_turn_start relies on LangGraph's checkpoint metadata["source"] == "input" to find
  the one checkpoint per user turn (as opposed to the several internal
  worker/tools/evaluator loop checkpoints within a single turn) -- this is the load-bearing
  assumption behind the whole feature, so it's asserted directly.
- retry_stream() forks from that checkpoint with an edited HumanMessage (same id, so
  LangGraph's add_messages reducer overwrites in place) and regenerates; message_store
  (the flat log GET /history reads) should end up containing only the edited turn, not the
  turns that came after the one being retried.

Run with:
    pytest backend/tests/test_time_travel.py
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import MemorySaver

from agent import AgentGraph
from chatbot import ChatbotManager
from session_repository import SessionRepository


def _mocked_bundle(worker_responses):
    worker_llm = FakeListChatModel(responses=worker_responses)
    evaluator_llm = MagicMock()
    evaluator_llm.invoke.return_value = MagicMock(
        feedback="looks complete", success_criteria_met=True, user_input_needed=False,
    )
    return {
        "model": MagicMock(),
        "worker_llm_with_tools": worker_llm,
        "evaluator_llm_with_output": evaluator_llm,
    }


def _build_manager(db_path: str, worker_responses: list) -> ChatbotManager:
    manager = ChatbotManager.__new__(ChatbotManager)
    manager.connection_string = f"sqlite:///{db_path}"
    manager.session_repo = SessionRepository(db_path)
    bundle = _mocked_bundle(worker_responses)
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


class TestFindTurnStart(_TempDbTestCase):
    def test_one_snapshot_per_chat_call_in_chronological_order(self):
        manager = _build_manager(self.db_path, ["first answer", "second answer"])
        session_id = "session-a"
        manager.chat(session_id, "first question")
        manager.chat(session_id, "second question")

        turn0 = manager._find_turn_start(session_id, 0)
        turn1 = manager._find_turn_start(session_id, 1)

        self.assertIn("first question", turn0.values["messages"][-1].content)
        self.assertIn("second question", turn1.values["messages"][-1].content)
        with self.assertRaises(ValueError):
            manager._find_turn_start(session_id, 2)


class TestRetryStream(_TempDbTestCase):
    def test_retry_edits_turn_and_drops_later_turns(self):
        manager = _build_manager(self.db_path, ["first answer", "second answer", "edited answer"])
        session_id = "session-a"
        manager.chat(session_id, "first question")
        manager.chat(session_id, "second question")

        full_response = "".join(manager.retry_stream(session_id, 0, "edited question"))

        self.assertEqual(full_response, "edited answer")

        state = manager.graph.get_state({"configurable": {"thread_id": session_id}})
        human_messages = [m for m in state.values["messages"] if m.type == "human"]
        self.assertEqual(len(human_messages), 1)
        self.assertIn("edited question", human_messages[0].content)
        self.assertNotIn("second question", str(state.values["messages"]))

        history = manager._get_session_history(session_id).messages
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].content, "edited question")
        self.assertEqual(history[1].content, "edited answer")


if __name__ == "__main__":
    unittest.main(verbosity=2)

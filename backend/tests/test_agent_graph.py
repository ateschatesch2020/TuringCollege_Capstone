"""Characterization tests for agent.AgentGraph -- the LangGraph worker/tools/evaluator/
timeout_notice graph extracted from chatbot.py's ChatbotManager (Phase 3 of the backend
refactor: chatbot.py:ChatbotManager was a God Class mixing graph orchestration, LLM
bundling, and session persistence; the graph-node logic now lives here).

Exercises the graph end-to-end (worker -> evaluator -> END, and
worker -> tools -> worker -> evaluator -> END) against a fully mocked LLM bundle, so it
runs without live API keys, SQLite files, or embedding models -- this is the first
automated coverage of this graph loop; previously only _close_orphaned_tool_calls had a
unit test in isolation.

Run with:
    pytest backend/tests/test_agent_graph.py
"""

import time
import unittest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from agent import AgentGraph


def _initial_state():
    return {
        "messages": [HumanMessage(content="hello")],
        "success_criteria": "",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
        "tool_retry_deadline": None,
    }


def _config(thread_id="t1", model_id="test-model"):
    return {"configurable": {"thread_id": thread_id, "model_id": model_id}}


def _bundle(worker_llm=None, evaluator_llm=None, model=None):
    return {
        "model": model or MagicMock(),
        "worker_llm_with_tools": worker_llm or MagicMock(),
        "evaluator_llm_with_output": evaluator_llm or MagicMock(),
    }


class TestAgentGraphHappyPath(unittest.TestCase):
    def test_worker_then_evaluator_ends_on_success(self):
        worker_llm = MagicMock()
        worker_llm.invoke.return_value = AIMessage(content="final answer")

        evaluator_llm = MagicMock()
        evaluator_llm.invoke.return_value = MagicMock(
            feedback="looks complete", success_criteria_met=True, user_input_needed=False,
        )

        agent_graph = AgentGraph(
            get_bundle=lambda model_id: _bundle(worker_llm, evaluator_llm),
            tools=[],
            checkpointer=MemorySaver(),
        )

        result = agent_graph.graph.invoke(_initial_state(), config=_config())

        contents = [m.content for m in result["messages"] if getattr(m, "content", None)]
        self.assertIn("final answer", contents)
        self.assertTrue(any("Evaluator Feedback" in c for c in contents))
        self.assertTrue(result["success_criteria_met"])
        worker_llm.invoke.assert_called_once()
        evaluator_llm.invoke.assert_called_once()


class TestAgentGraphToolCallPath(unittest.TestCase):
    def test_worker_calls_tool_then_reevaluates(self):
        @tool
        def dummy_tool(x: str) -> str:
            """A dummy tool for testing the tools-loop edge."""
            return f"tool result for {x}"

        worker_llm = MagicMock()
        tool_call_msg = AIMessage(content="", tool_calls=[
            {"name": "dummy_tool", "args": {"x": "abc"}, "id": "call_1", "type": "tool_call"}
        ])
        final_msg = AIMessage(content="done using tool")
        worker_llm.invoke.side_effect = [tool_call_msg, final_msg]

        evaluator_llm = MagicMock()
        evaluator_llm.invoke.return_value = MagicMock(
            feedback="ok", success_criteria_met=True, user_input_needed=False,
        )

        agent_graph = AgentGraph(
            get_bundle=lambda model_id: _bundle(worker_llm, evaluator_llm),
            tools=[dummy_tool],
            checkpointer=MemorySaver(),
        )

        result = agent_graph.graph.invoke(_initial_state(), config=_config(thread_id="t2"))

        self.assertEqual(worker_llm.invoke.call_count, 2)
        contents = [m.content for m in result["messages"] if getattr(m, "content", None)]
        self.assertIn("tool result for abc", contents)
        self.assertIn("done using tool", contents)
        self.assertTrue(result["success_criteria_met"])


class TestTimeoutNotice(unittest.TestCase):
    def test_returns_explanation_and_doubles_timeout(self):
        model = MagicMock()
        model.invoke.return_value = AIMessage(content="explanation to user")

        agent_graph = AgentGraph(
            get_bundle=lambda model_id: _bundle(model=model),
            tools=[],
            checkpointer=MemorySaver(),
        )

        state = {
            "messages": [ToolMessage(content="Error: boom", tool_call_id="1")],
            "tool_retry_timeout_seconds": 30,
        }
        result = agent_graph.timeout_notice(state, _config())

        self.assertEqual(result["messages"][0].content, "explanation to user")
        self.assertTrue(result["user_input_needed"])
        self.assertFalse(result["success_criteria_met"])
        self.assertEqual(result["tool_retry_timeout_seconds"], 60)


class TestWorkerRouter(unittest.TestCase):
    def setUp(self):
        # worker_router doesn't touch self at all, so building a graph is unnecessary.
        self.agent_graph = AgentGraph.__new__(AgentGraph)

    def test_routes_to_tools_when_tool_calls_pending_and_deadline_not_passed(self):
        state = {
            "messages": [AIMessage(content="", tool_calls=[
                {"name": "x", "args": {}, "id": "1", "type": "tool_call"},
            ])],
            "tool_retry_deadline": time.time() + 30,
        }
        self.assertEqual(self.agent_graph.worker_router(state), "tools")

    def test_routes_to_timeout_when_deadline_passed(self):
        state = {
            "messages": [AIMessage(content="", tool_calls=[
                {"name": "x", "args": {}, "id": "1", "type": "tool_call"},
            ])],
            "tool_retry_deadline": time.time() - 1,
        }
        self.assertEqual(self.agent_graph.worker_router(state), "timeout")

    def test_routes_to_evaluator_when_no_tool_calls(self):
        state = {"messages": [AIMessage(content="done")], "tool_retry_deadline": None}
        self.assertEqual(self.agent_graph.worker_router(state), "evaluator")


class TestRouteBasedOnEvaluation(unittest.TestCase):
    def setUp(self):
        self.agent_graph = AgentGraph.__new__(AgentGraph)

    def test_routes_to_end_when_success_criteria_met(self):
        state = {"success_criteria_met": True, "user_input_needed": False}
        self.assertEqual(self.agent_graph.route_based_on_evaluation(state), "END")

    def test_routes_to_end_when_user_input_needed(self):
        state = {"success_criteria_met": False, "user_input_needed": True}
        self.assertEqual(self.agent_graph.route_based_on_evaluation(state), "END")

    def test_routes_back_to_worker_otherwise(self):
        state = {"success_criteria_met": False, "user_input_needed": False}
        self.assertEqual(self.agent_graph.route_based_on_evaluation(state), "worker")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Unit tests for tools.ToolRegistry / tools.build_tool_registry (Phase 5 of the
backend refactor). Previously the agent's tool list was assembled in 3 disconnected
places: tools.py's Tools.tools class attribute, 3 manual .append() calls in
ChatbotManager.__init__, and hardcoded routing guidance in agent.py's worker system
prompt. build_tool_registry() now builds the tool list and its prompt-routing text
together from one place.

Run with:
    pytest backend/tests/test_tool_registry.py
"""

import unittest
from unittest.mock import MagicMock

from tools import ToolRegistry, build_tool_registry


class TestToolRegistry(unittest.TestCase):
    def test_register_single_tool(self):
        registry = ToolRegistry()
        registry.register("tool_a", "• tool_a: does A things.")
        self.assertEqual(registry.tools, ["tool_a"])
        self.assertEqual(registry.routing_text, "• tool_a: does A things.")

    def test_register_grouped_tools_share_one_routing_entry(self):
        registry = ToolRegistry()
        registry.register(("tool_b", "tool_c"), "• tool_b / tool_c: does BC things.")
        self.assertEqual(registry.tools, ["tool_b", "tool_c"])
        self.assertEqual(registry.routing_text, "• tool_b / tool_c: does BC things.")

    def test_tools_preserves_registration_order_across_entries(self):
        registry = ToolRegistry()
        registry.register("first", "first routing")
        registry.register(("second", "third"), "second/third routing")
        self.assertEqual(registry.tools, ["first", "second", "third"])

    def test_routing_text_joins_entries_with_blank_line(self):
        registry = ToolRegistry()
        registry.register("a", "routing a")
        registry.register("b", "routing b")
        self.assertEqual(registry.routing_text, "routing a\n\nrouting b")


class TestBuildToolRegistry(unittest.TestCase):
    def test_includes_all_expected_tools_by_name(self):
        registry = build_tool_registry(
            resolve_embedding=MagicMock(),
            rerank_llm=MagicMock(),
            session_docs_dir="/tmp/sessions",
        )
        tool_names = {t.name for t in registry.tools}
        self.assertEqual(
            tool_names,
            {
                "search_documents", "hybrid_search_documents", "list_uploaded_documents",
                "web_search", "generate_presentation", "generate_word_document", "generate_pdf_document",
            },
        )

    def test_routing_text_mentions_every_tool_name(self):
        registry = build_tool_registry(
            resolve_embedding=MagicMock(),
            rerank_llm=MagicMock(),
            session_docs_dir="/tmp/sessions",
        )
        for tool in registry.tools:
            self.assertIn(tool.name, registry.routing_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

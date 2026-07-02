"""
Unit tests for hybrid document search (tools.py):
  - _keyword_search: keyword/FTS candidate retrieval and ranking
  - _llm_rerank: single-call listwise LLM re-ranking
  - hybrid_retrieve: merges/dedupes/reranks semantic + keyword candidates, filterable
  - hybrid_search_documents (via make_hybrid_search_tool): end-to-end tool behavior

Run with:
    pytest backend/tests/test_hybrid_search.py
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from tools import _keyword_search, _llm_rerank, hybrid_retrieve, make_hybrid_search_tool


# ---------------------------------------------------------------------------
# _keyword_search
# ---------------------------------------------------------------------------

class TestKeywordSearch(unittest.TestCase):

    def test_ranks_by_keyword_occurrence_count(self):
        vs = MagicMock()
        vs.get.return_value = {
            "documents": ["apple apple banana", "apple banana banana banana", "no match here"],
            "metadatas": [{}, {}, {}],
        }
        results = _keyword_search(vs, "apple banana", k=10)
        self.assertEqual(
            [d.page_content for d in results],
            ["apple banana banana banana", "apple apple banana", "no match here"],
        )

    def test_caps_results_at_k(self):
        vs = MagicMock()
        vs.get.return_value = {
            "documents": ["apple " * (i + 1) for i in range(5)],
            "metadatas": [{}] * 5,
        }
        results = _keyword_search(vs, "apple", k=2)
        self.assertEqual(len(results), 2)

    def test_single_token_uses_contains_not_or(self):
        vs = MagicMock()
        vs.get.return_value = {"documents": [], "metadatas": []}
        _keyword_search(vs, "keyword", k=10)
        called_where = vs.get.call_args.kwargs["where_document"]
        self.assertEqual(called_where, {"$contains": "keyword"})

    def test_multi_token_uses_or_of_contains(self):
        vs = MagicMock()
        vs.get.return_value = {"documents": [], "metadatas": []}
        _keyword_search(vs, "first second", k=10)
        called_where = vs.get.call_args.kwargs["where_document"]
        self.assertEqual(called_where, {"$or": [{"$contains": "first"}, {"$contains": "second"}]})

    def test_short_tokens_are_ignored(self):
        vs = MagicMock()
        results = _keyword_search(vs, "a of", k=10)
        vs.get.assert_not_called()
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# _llm_rerank
# ---------------------------------------------------------------------------

class TestLlmRerank(unittest.TestCase):

    def _candidates(self, n):
        return [Document(page_content=f"chunk {i}") for i in range(n)]

    def test_reorders_by_llm_indices(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="[2, 0, 1]")
        candidates = self._candidates(3)
        result = _llm_rerank(llm, "query", candidates, k=3)
        self.assertEqual([d.page_content for d in result], ["chunk 2", "chunk 0", "chunk 1"])

    def test_truncates_to_k(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="[0, 1, 2, 3, 4]")
        candidates = self._candidates(5)
        result = _llm_rerank(llm, "query", candidates, k=2)
        self.assertEqual(len(result), 2)

    def test_falls_back_to_first_k_on_unparsable_output(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="not json")
        candidates = self._candidates(5)
        result = _llm_rerank(llm, "query", candidates, k=3)
        self.assertEqual([d.page_content for d in result], ["chunk 0", "chunk 1", "chunk 2"])

    def test_falls_back_when_llm_raises(self):
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("boom")
        candidates = self._candidates(4)
        result = _llm_rerank(llm, "query", candidates, k=2)
        self.assertEqual([d.page_content for d in result], ["chunk 0", "chunk 1"])

    def test_ignores_out_of_range_and_duplicate_indices(self):
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="[99, 0, 0, 1]")
        candidates = self._candidates(3)
        result = _llm_rerank(llm, "query", candidates, k=3)
        self.assertEqual([d.page_content for d in result], ["chunk 0", "chunk 1"])


# ---------------------------------------------------------------------------
# hybrid_retrieve
# ---------------------------------------------------------------------------

class TestHybridRetrieve(unittest.TestCase):

    def test_merges_and_dedupes_without_llm_when_few_candidates(self):
        vs = MagicMock()
        vs.similarity_search.return_value = [Document(page_content="chunk A")]
        vs.get.return_value = {"documents": ["chunk A", "chunk B"], "metadatas": [{}, {}]}
        llm = MagicMock()

        result = hybrid_retrieve(vs, "query", llm, k=5, candidate_k=10)

        llm.invoke.assert_not_called()
        self.assertEqual([d.page_content for d in result], ["chunk A", "chunk B"])

    def test_calls_llm_rerank_when_more_candidates_than_k(self):
        vs = MagicMock()
        vs.similarity_search.return_value = [Document(page_content=f"sem {i}") for i in range(4)]
        vs.get.return_value = {"documents": [f"kw {i}" for i in range(4)], "metadatas": [{}] * 4}
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="[0, 1, 2, 3, 4]")

        result = hybrid_retrieve(vs, "query", llm, k=5, candidate_k=10)

        llm.invoke.assert_called_once()
        self.assertEqual(len(result), 5)

    def test_returns_empty_list_when_no_candidates(self):
        vs = MagicMock()
        vs.similarity_search.return_value = []
        vs.get.return_value = {"documents": [], "metadatas": []}
        llm = MagicMock()

        result = hybrid_retrieve(vs, "query", llm, k=5, candidate_k=10)

        self.assertEqual(result, [])

    def test_forwards_filter_to_semantic_and_keyword_search(self):
        vs = MagicMock()
        vs.similarity_search.return_value = []
        vs.get.return_value = {"documents": [], "metadatas": []}
        llm = MagicMock()
        doc_filter = {"source": "/docs/report.pdf"}

        hybrid_retrieve(vs, "query", llm, k=5, candidate_k=10, filter=doc_filter)

        vs.similarity_search.assert_called_once_with("query", k=10, filter=doc_filter)
        self.assertEqual(vs.get.call_args.kwargs["where"], doc_filter)


# ---------------------------------------------------------------------------
# hybrid_search_documents tool
# ---------------------------------------------------------------------------

class TestHybridSearchTool(unittest.TestCase):

    def _invoke(self, tool_obj, query, session_id="sess1"):
        return tool_obj.invoke({"query": query}, config={"configurable": {"thread_id": session_id}})

    def test_returns_no_info_when_no_session_id(self):
        tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=MagicMock(), sessions_dir="/tmp")
        result = tool_obj.invoke({"query": "hi"}, config={"configurable": {}})
        self.assertEqual(result, "No relevant information found in uploaded documents.")

    def test_returns_no_info_when_session_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=MagicMock(), sessions_dir=tmpdir)
            result = self._invoke(tool_obj, "hi", session_id="nonexistent")
        self.assertEqual(result, "No relevant information found in uploaded documents.")

    @patch("tools.Chroma")
    def test_merges_semantic_and_keyword_results_without_llm_when_few_candidates(self, mock_chroma_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sess1"))
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [Document(page_content="chunk A")]
            mock_vs.get.return_value = {"documents": ["chunk B"], "metadatas": [{}]}
            mock_chroma_cls.return_value = mock_vs

            llm = MagicMock()
            tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=llm, sessions_dir=tmpdir)
            result = self._invoke(tool_obj, "chunk")

        llm.invoke.assert_not_called()
        self.assertIn("chunk A", result)
        self.assertIn("chunk B", result)

    @patch("tools.Chroma")
    def test_dedupes_overlapping_semantic_and_keyword_results(self, mock_chroma_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sess1"))
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [Document(page_content="same chunk")]
            mock_vs.get.return_value = {"documents": ["same chunk"], "metadatas": [{}]}
            mock_chroma_cls.return_value = mock_vs

            tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=MagicMock(), sessions_dir=tmpdir)
            result = self._invoke(tool_obj, "same chunk")

        self.assertEqual(result.count("same chunk"), 1)

    @patch("tools.Chroma")
    def test_calls_llm_rerank_when_more_than_five_candidates(self, mock_chroma_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sess1"))
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = [Document(page_content=f"sem {i}") for i in range(4)]
            mock_vs.get.return_value = {
                "documents": [f"kw {i}" for i in range(4)],
                "metadatas": [{}] * 4,
            }
            mock_chroma_cls.return_value = mock_vs

            llm = MagicMock()
            llm.invoke.return_value = MagicMock(content="[0, 1, 2, 3, 4]")
            tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=llm, sessions_dir=tmpdir)
            self._invoke(tool_obj, "sem kw")

        llm.invoke.assert_called_once()

    @patch("tools.Chroma")
    def test_returns_no_info_when_no_candidates_found(self, mock_chroma_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "sess1"))
            mock_vs = MagicMock()
            mock_vs.similarity_search.return_value = []
            mock_vs.get.return_value = {"documents": [], "metadatas": []}
            mock_chroma_cls.return_value = mock_vs

            tool_obj = make_hybrid_search_tool(embedding_model=MagicMock(), llm=MagicMock(), sessions_dir=tmpdir)
            result = self._invoke(tool_obj, "nothing")

        self.assertEqual(result, "No relevant information found in uploaded documents.")


if __name__ == "__main__":
    unittest.main(verbosity=2)

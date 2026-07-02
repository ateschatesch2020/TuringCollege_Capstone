"""
Unit tests for backend/rag/ragas_evaluator.py's evaluate_document():
  - Runs a plain-semantic evaluation pass (existing behavior)
  - Runs a second, independent hybrid-search evaluation pass per question,
    scored the same way, and nested under a "hybrid" key in each result.

Run with:
    pytest backend/tests/test_ragas_evaluator.py
"""

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.documents import Document

# rag_vector_db.py (imported transitively by ragas_evaluator.py) pulls in optional
# heavy deps that may not be installed in every dev environment; stub them out so
# this test only exercises ragas_evaluator's own logic, not those dependencies.
sys.modules.setdefault("pymupdf4llm", MagicMock())
sys.modules.setdefault("langchain_experimental", MagicMock())
sys.modules.setdefault("langchain_experimental.text_splitter", MagicMock())

from rag.ragas_evaluator import evaluate_document  # noqa: E402


class TestEvaluateDocumentHybridSection(unittest.TestCase):

    @patch("rag.ragas_evaluator._score_context_recall", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_context_precision", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_answer_relevancy", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_faithfulness", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator.hybrid_retrieve")
    @patch("rag.ragas_evaluator.generate_qa_pairs", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._load_pdf")
    @patch("rag.ragas_evaluator._get_embedding_model")
    @patch("rag.ragas_evaluator.Chroma")
    @patch("rag.ragas_evaluator._get_llm")
    def test_result_includes_independent_hybrid_section(
        self, mock_get_llm, mock_chroma_cls, mock_get_emb, mock_load_pdf,
        mock_gen_qa, mock_hybrid_retrieve,
        mock_score_faithfulness, mock_score_relevancy, mock_score_precision, mock_score_recall,
    ):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=[
            MagicMock(content="plain answer"),
            MagicMock(content="hybrid answer"),
        ])
        mock_get_llm.return_value = llm

        mock_load_pdf.return_value = [Document(page_content="full document text")]
        mock_gen_qa.return_value = [{"question": "What is X?", "answer": "X is Y"}]

        mock_vectorstore = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [Document(page_content="plain chunk")]
        mock_vectorstore.as_retriever.return_value = mock_retriever
        mock_chroma_cls.return_value = mock_vectorstore

        mock_hybrid_retrieve.return_value = [Document(page_content="hybrid chunk")]

        mock_score_faithfulness.side_effect = [0.7, 0.4]
        mock_score_relevancy.side_effect = [0.6, 0.3]
        mock_score_precision.side_effect = [0.5, 0.2]
        mock_score_recall.side_effect = [0.9, 0.1]

        results = self._run(evaluate_document(
            file_path="/docs/report.pdf",
            persist_directory="/chroma/sess1",
            num_questions=1,
        ))

        self.assertEqual(len(results), 1)
        result = results[0]

        # Plain (semantic) section untouched
        self.assertEqual(result["rag_answer"], "plain answer")
        self.assertEqual(result["faithfulness"], 0.7)
        self.assertEqual(result["answer_relevancy"], 0.6)
        self.assertEqual(result["context_precision"], 0.5)
        self.assertEqual(result["context_recall"], 0.9)

        # New hybrid section, independently scored
        self.assertIn("hybrid", result)
        hybrid = result["hybrid"]
        self.assertEqual(hybrid["rag_answer"], "hybrid answer")
        self.assertEqual(hybrid["faithfulness"], 0.4)
        self.assertEqual(hybrid["answer_relevancy"], 0.3)
        self.assertEqual(hybrid["context_precision"], 0.2)
        self.assertEqual(hybrid["context_recall"], 0.1)

        # hybrid_retrieve was scoped to the document being evaluated
        mock_hybrid_retrieve.assert_called_once_with(
            mock_vectorstore, "What is X?", llm, 5, 10, {"source": "/docs/report.pdf"}
        )

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main(verbosity=2)

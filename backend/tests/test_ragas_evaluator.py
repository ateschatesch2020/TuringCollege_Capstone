"""
Unit tests for backend/rag/ragas_evaluator.py's evaluate_document():
  - Runs whichever (chunking, search) strategies are requested independently per question,
    each scored the same way, nested under its own key in each result's "results" dict.

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
sys.modules.setdefault("langchain_text_splitters", MagicMock())

from rag.ragas_evaluator import evaluate_document  # noqa: E402


class TestEvaluateDocumentStrategies(unittest.TestCase):

    @patch("rag.ragas_evaluator._score_context_recall", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_context_precision", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_answer_relevancy", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_faithfulness", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator.hybrid_retrieve")
    @patch("rag.ragas_evaluator.generate_qa_pairs", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._load_document")
    @patch("rag.ragas_evaluator.get_embedding_model")
    @patch("rag.ragas_evaluator.Chroma")
    @patch("rag.ragas_evaluator._get_llm")
    def test_result_includes_semantic_and_hybrid_sections(
        self, mock_get_llm, mock_chroma_cls, mock_get_emb, mock_load_document,
        mock_gen_qa, mock_hybrid_retrieve,
        mock_score_faithfulness, mock_score_relevancy, mock_score_precision, mock_score_recall,
    ):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=[
            MagicMock(content="plain answer"),
            MagicMock(content="hybrid answer"),
        ])
        mock_get_llm.return_value = llm

        mock_load_document.return_value = [Document(page_content="full document text")]
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
            answer_model_id="openai/gpt-4o",
            judge_model_id="openai/gpt-4o",
            strategies=["semantic", "semantic_hybrid"],
            session_id="sess1",
        ))

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(set(result["results"].keys()), {"semantic", "semantic_hybrid"})

        semantic = result["results"]["semantic"]
        self.assertEqual(semantic["rag_answer"], "plain answer")
        self.assertEqual(semantic["faithfulness"], 0.7)
        self.assertEqual(semantic["answer_relevancy"], 0.6)
        self.assertEqual(semantic["context_precision"], 0.5)
        self.assertEqual(semantic["context_recall"], 0.9)

        hybrid = result["results"]["semantic_hybrid"]
        self.assertEqual(hybrid["rag_answer"], "hybrid answer")
        self.assertEqual(hybrid["faithfulness"], 0.4)
        self.assertEqual(hybrid["answer_relevancy"], 0.3)
        self.assertEqual(hybrid["context_precision"], 0.2)
        self.assertEqual(hybrid["context_recall"], 0.1)

        mock_hybrid_retrieve.assert_called_once_with(
            mock_vectorstore, "What is X?", llm, 5, 10, {"source": "/docs/report.pdf"}
        )

    @patch("rag.ragas_evaluator._score_context_recall", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_context_precision", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_answer_relevancy", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._score_faithfulness", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator.hybrid_retrieve")
    @patch("rag.ragas_evaluator.ensure_recursive_chunks")
    @patch("rag.ragas_evaluator.generate_qa_pairs", new_callable=AsyncMock)
    @patch("rag.ragas_evaluator._load_document")
    @patch("rag.ragas_evaluator.get_embedding_model")
    @patch("rag.ragas_evaluator.Chroma")
    @patch("rag.ragas_evaluator._get_llm")
    def test_recursive_strategies_ensure_chunks_and_use_recursive_store(
        self, mock_get_llm, mock_chroma_cls, mock_get_emb, mock_load_document,
        mock_gen_qa, mock_ensure_recursive_chunks, mock_hybrid_retrieve,
        mock_score_faithfulness, mock_score_relevancy, mock_score_precision, mock_score_recall,
    ):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=[
            MagicMock(content="recursive answer"),
            MagicMock(content="recursive hybrid answer"),
        ])
        mock_get_llm.return_value = llm

        mock_load_document.return_value = [Document(page_content="full document text")]
        mock_gen_qa.return_value = [{"question": "What is X?", "answer": "X is Y"}]

        mock_ensure_recursive_chunks.return_value = "/chroma/shared_recursive"

        mock_vectorstore = MagicMock()
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [Document(page_content="recursive chunk")]
        mock_vectorstore.as_retriever.return_value = mock_retriever
        mock_chroma_cls.return_value = mock_vectorstore

        mock_hybrid_retrieve.return_value = [Document(page_content="recursive hybrid chunk")]

        mock_score_faithfulness.side_effect = [0.7, 0.4]
        mock_score_relevancy.side_effect = [0.6, 0.3]
        mock_score_precision.side_effect = [0.5, 0.2]
        mock_score_recall.side_effect = [0.9, 0.1]

        results = self._run(evaluate_document(
            file_path="/docs/report.pdf",
            persist_directory="/chroma/sess1",
            num_questions=1,
            answer_model_id="openai/gpt-4o",
            judge_model_id="openai/gpt-4o",
            strategies=["recursive", "recursive_hybrid"],
            session_id="sess1",
        ))

        mock_ensure_recursive_chunks.assert_called_once_with("/docs/report.pdf", "sess1", None)
        mock_chroma_cls.assert_called_once_with(persist_directory="/chroma/shared_recursive", embedding_function=mock_get_emb.return_value)

        result = results[0]
        self.assertEqual(set(result["results"].keys()), {"recursive", "recursive_hybrid"})
        self.assertEqual(result["results"]["recursive"]["rag_answer"], "recursive answer")
        self.assertEqual(result["results"]["recursive_hybrid"]["rag_answer"], "recursive hybrid answer")

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main(verbosity=2)

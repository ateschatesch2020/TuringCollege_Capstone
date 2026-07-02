"""
Unit tests for document management:
  - rag.rag_vector_db: delete_document
  - api.py: GET /documents, POST /documents/upload, DELETE /documents/{filename}

All document endpoints are session-scoped — every request requires session_id.

Run with:
    pytest backend/tests/test_documents.py
"""

import json as _json
import sys
import os
import unittest
import tempfile
from unittest.mock import MagicMock, patch


def _parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            try:
                events.append(_json.loads(line[5:].strip()))
            except _json.JSONDecodeError:
                pass
    return events

# Mock chatbot before importing api — ChatbotManager is instantiated at module
# level in api.py and transitively pulls in tools/serpapi/ortools.
_chatbot_instance = MagicMock()
sys.modules["chatbot"] = MagicMock(
    ChatbotManager=MagicMock(return_value=_chatbot_instance)
)

from fastapi.testclient import TestClient  # noqa: E402
import api  # noqa: E402  (chatbot already mocked above)
from api import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument(unittest.TestCase):

    @patch("rag.rag_vector_db.Chroma")
    @patch("rag.rag_vector_db._get_embedding_model")
    def test_filters_by_source_and_deletes_ids(self, mock_emb, mock_chroma_cls):
        mock_vs = MagicMock()
        mock_vs.get.return_value = {"ids": ["id1", "id2", "id3"]}
        mock_chroma_cls.return_value = mock_vs

        from rag.rag_vector_db import delete_document
        result = delete_document("/docs/test.pdf", "/chroma")

        mock_vs.get.assert_called_once_with(where={"source": "/docs/test.pdf"})
        mock_vs.delete.assert_called_once_with(["id1", "id2", "id3"])
        self.assertEqual(result, 3)

    @patch("rag.rag_vector_db.Chroma")
    @patch("rag.rag_vector_db._get_embedding_model")
    def test_skips_delete_call_when_no_chunks_match(self, mock_emb, mock_chroma_cls):
        mock_vs = MagicMock()
        mock_vs.get.return_value = {"ids": []}
        mock_chroma_cls.return_value = mock_vs

        from rag.rag_vector_db import delete_document
        result = delete_document("/docs/missing.pdf", "/chroma")

        mock_vs.delete.assert_not_called()
        self.assertEqual(result, 0)

    @patch("rag.rag_vector_db.Chroma")
    @patch("rag.rag_vector_db._get_embedding_model")
    def test_returns_number_of_deleted_chunks(self, mock_emb, mock_chroma_cls):
        mock_vs = MagicMock()
        mock_vs.get.return_value = {"ids": ["a", "b"]}
        mock_chroma_cls.return_value = mock_vs

        from rag.rag_vector_db import delete_document
        self.assertEqual(delete_document("/docs/other.pdf", "/chroma"), 2)


# ---------------------------------------------------------------------------
# GET /documents
# ---------------------------------------------------------------------------

class TestListDocumentsEndpoint(unittest.TestCase):

    def test_returns_sorted_pdfs_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "test-session")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "guide.pdf"), "w").close()
            open(os.path.join(session_dir, "policy.pdf"), "w").close()
            open(os.path.join(session_dir, "notes.txt"), "w").close()
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.get("/documents", params={"session_id": "test-session"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["documents"], ["guide.pdf", "policy.pdf"])

    def test_returns_empty_list_when_directory_has_no_pdfs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "test-session")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "readme.txt"), "w").close()
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.get("/documents", params={"session_id": "test-session"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["documents"], [])

    def test_returns_empty_list_when_session_has_no_documents_yet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.get("/documents", params={"session_id": "never-uploaded-to"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["documents"], [])

    def test_requires_session_id(self):
        res = client.get("/documents")
        self.assertEqual(res.status_code, 422)


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------

class TestUploadDocumentEndpoint(unittest.TestCase):

    def setUp(self):
        _chatbot_instance.reset_mock()

    @patch("api.add_document_for_session", return_value=7)
    def test_upload_returns_filename_and_chunk_count(self, mock_add):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.post(
                    "/documents/upload",
                    files={"file": ("policy.pdf", b"%PDF content", "application/pdf")},
                    data={"session_id": "test-session"},
                )

        self.assertEqual(res.status_code, 200)
        events = _parse_sse(res.text)
        complete = next(e for e in events if e.get("stage") == "Complete")
        self.assertEqual(complete["filename"], "policy.pdf")
        self.assertEqual(complete["chunks"], 7)

    @patch("api.add_document_for_session", return_value=5)
    def test_upload_calls_add_document_for_session(self, mock_add):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                client.post(
                    "/documents/upload",
                    files={"file": ("policy.pdf", b"%PDF content", "application/pdf")},
                    data={"session_id": "test-session"},
                )

        mock_add.assert_called_once()
        self.assertEqual(mock_add.call_args.args[1], "test-session")

    def test_upload_rejects_non_pdf_with_400(self):
        res = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", b"text content", "text/plain")},
            data={"session_id": "test-session"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("PDF", res.json()["detail"])

    def test_upload_requires_session_id(self):
        res = client.post(
            "/documents/upload",
            files={"file": ("policy.pdf", b"%PDF content", "application/pdf")},
        )
        self.assertEqual(res.status_code, 422)


# ---------------------------------------------------------------------------
# DELETE /documents/{filename}
# ---------------------------------------------------------------------------

class TestDeleteDocumentEndpoint(unittest.TestCase):

    def setUp(self):
        _chatbot_instance.reset_mock()

    @patch("api.delete_document", return_value=4)
    def test_delete_returns_filename_and_chunks_removed(self, mock_del):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "test-session")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "policy.pdf"), "wb").close()
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.delete("/documents/policy.pdf", params={"session_id": "test-session"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["filename"], "policy.pdf")
        self.assertEqual(res.json()["chunks_removed"], 4)

    @patch("api.delete_document", return_value=3)
    def test_delete_calls_delete_document(self, mock_del):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "test-session")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "policy.pdf"), "wb").close()
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                client.delete("/documents/policy.pdf", params={"session_id": "test-session"})

        mock_del.assert_called_once()

    def test_delete_nonexistent_file_returns_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.delete("/documents/missing.pdf", params={"session_id": "test-session"})

        self.assertEqual(res.status_code, 404)

    def test_delete_requires_session_id(self):
        res = client.delete("/documents/policy.pdf")
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)

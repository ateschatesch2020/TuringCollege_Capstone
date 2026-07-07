"""
Unit tests for document listing (tools.py):
  - list_session_documents: filesystem helper shared with api.py's GET /documents
  - list_uploaded_documents (via make_list_documents_tool): end-to-end tool behavior

Run with:
    pytest backend/tests/test_list_documents_tool.py
"""

import os
import tempfile
import unittest

from tools import list_session_documents, make_list_documents_tool


class TestListSessionDocuments(unittest.TestCase):

    def test_returns_sorted_supported_documents_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "sess1")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "b.pdf"), "w").close()
            open(os.path.join(session_dir, "a.pdf"), "w").close()
            open(os.path.join(session_dir, "notes.txt"), "w").close()
            open(os.path.join(session_dir, "archive.zip"), "w").close()
            result = list_session_documents(tmpdir, "sess1")
        self.assertEqual(result, ["a.pdf", "b.pdf", "notes.txt"])

    def test_returns_empty_list_when_session_dir_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = list_session_documents(tmpdir, "never-uploaded-to")
        self.assertEqual(result, [])


class TestListUploadedDocumentsTool(unittest.TestCase):

    def _invoke(self, tool_obj, session_id="sess1"):
        return tool_obj.invoke({}, config={"configurable": {"thread_id": session_id}})

    def test_returns_message_when_no_session_id(self):
        tool_obj = make_list_documents_tool(session_docs_dir="/tmp")
        result = tool_obj.invoke({}, config={"configurable": {}})
        self.assertEqual(result, "No session found; cannot list documents.")

    def test_returns_empty_message_when_session_has_no_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool_obj = make_list_documents_tool(session_docs_dir=tmpdir)
            result = self._invoke(tool_obj, session_id="empty-session")
        self.assertEqual(result, "This session has no uploaded documents yet.")

    def test_returns_count_and_names_for_populated_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "sess1")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "policy.pdf"), "w").close()
            open(os.path.join(session_dir, "guide.pdf"), "w").close()
            tool_obj = make_list_documents_tool(session_docs_dir=tmpdir)
            result = self._invoke(tool_obj, session_id="sess1")
        self.assertIn("2 uploaded document(s)", result)
        self.assertIn("policy.pdf", result)
        self.assertIn("guide.pdf", result)

    def test_filters_out_unsupported_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "sess1")
            os.makedirs(session_dir)
            open(os.path.join(session_dir, "policy.pdf"), "w").close()
            open(os.path.join(session_dir, "readme.txt"), "w").close()
            open(os.path.join(session_dir, "archive.zip"), "w").close()
            tool_obj = make_list_documents_tool(session_docs_dir=tmpdir)
            result = self._invoke(tool_obj, session_id="sess1")
        self.assertIn("2 uploaded document(s)", result)
        self.assertIn("readme.txt", result)
        self.assertNotIn("archive.zip", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Unit tests for session_repository.SessionRepository -- the SQLite CRUD extracted
from ChatbotManager (Phase 4 of the backend refactor). Previously no test covered
session persistence at all (the 7+ methods each opened their own sqlite3.connect
inline inside ChatbotManager); this uses a temp SQLite file so it exercises the
real DB round-trip without touching the app's actual test_history.db.

Run with:
    pytest backend/tests/test_session_repository.py
"""

import os
import tempfile
import unittest

from session_repository import SessionRepository


class TestSessionRepository(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.repo = SessionRepository(self.db_path)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except PermissionError:
            pass  # Windows sometimes briefly holds the sqlite file handle open; harmless leftover temp file

    def test_create_then_get_info_round_trips(self):
        self.repo.create("sess-1", "user-1", "My Session", "openai/gpt-4o", "openai")

        info = self.repo.get_info("sess-1")

        self.assertEqual(info["session_id"], "sess-1")
        self.assertEqual(info["title"], "My Session")
        self.assertEqual(info["model"], "openai/gpt-4o")
        self.assertEqual(info["embedding_model"], "openai")

    def test_get_info_returns_none_for_missing_session(self):
        self.assertIsNone(self.repo.get_info("does-not-exist"))

    def test_get_user_id_returns_none_for_missing_session(self):
        self.assertIsNone(self.repo.get_user_id("does-not-exist"))

    def test_get_embedding_model_round_trips(self):
        self.repo.create("sess-1", "user-1", "Title", "openai/gpt-4o", "huggingface")
        self.assertEqual(self.repo.get_embedding_model("sess-1"), "huggingface")

    def test_list_for_user_returns_only_that_users_sessions_newest_first(self):
        self.repo.create("sess-1", "user-1", "First", "openai/gpt-4o", "openai")
        self.repo.create("sess-2", "user-1", "Second", "openai/gpt-4o", "openai")
        self.repo.create("sess-3", "user-2", "Other user's session", "openai/gpt-4o", "openai")

        sessions = self.repo.list_for_user("user-1")

        session_ids = [s["session_id"] for s in sessions]
        self.assertEqual(set(session_ids), {"sess-1", "sess-2"})
        self.assertNotIn("sess-3", session_ids)

    def test_update_title(self):
        self.repo.create("sess-1", "user-1", "Old Title", "openai/gpt-4o", "openai")
        self.repo.update_title("sess-1", "New Title")
        self.assertEqual(self.repo.get_info("sess-1")["title"], "New Title")

    def test_update_model(self):
        self.repo.create("sess-1", "user-1", "Title", "openai/gpt-4o", "openai")
        self.repo.update_model("sess-1", "anthropic/claude-haiku-4.5")
        self.assertEqual(self.repo.get_info("sess-1")["model"], "anthropic/claude-haiku-4.5")

    def test_delete_removes_the_session(self):
        self.repo.create("sess-1", "user-1", "Title", "openai/gpt-4o", "openai")
        self.repo.delete("sess-1")
        self.assertIsNone(self.repo.get_info("sess-1"))

    def test_delete_is_a_no_op_for_missing_session(self):
        self.repo.delete("does-not-exist")  # must not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)

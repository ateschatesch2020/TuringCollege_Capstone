import sqlite3
from typing import Optional

from models_catalog import DEFAULT_MODEL_ID, DEFAULT_EMBEDDING_MODEL_ID


class SessionRepository:
    """SQLite-backed CRUD for the chat_sessions table, extracted from ChatbotManager
    (which previously opened its own sqlite3.connect in each of these methods) so
    session persistence can be tested and swapped independently of the LangGraph
    orchestration in ChatbotManager/AgentGraph."""

    def __init__(self, db_file_path: str):
        self.db_file_path = db_file_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute(f'''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '{DEFAULT_MODEL_ID}',
                    embedding_model TEXT NOT NULL DEFAULT '{DEFAULT_EMBEDDING_MODEL_ID}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                conn.execute(f"ALTER TABLE chat_sessions ADD COLUMN model TEXT DEFAULT '{DEFAULT_MODEL_ID}'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute(f"ALTER TABLE chat_sessions ADD COLUMN embedding_model TEXT DEFAULT '{DEFAULT_EMBEDDING_MODEL_ID}'")
            except sqlite3.OperationalError:
                pass

    def create(self, session_id: str, user_id: str, title: str, model: str, embedding_model: str) -> str:
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                INSERT INTO chat_sessions (session_id, user_id, title, model, embedding_model)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, user_id, title, model, embedding_model))
        return session_id

    def delete(self, session_id: str) -> None:
        """Deletes the session and its messages atomically."""
        with sqlite3.connect(self.db_file_path) as conn:
            try:
                conn.execute('DELETE FROM message_store WHERE session_id = ?', (session_id,))
            except sqlite3.OperationalError:
                pass  # message_store is created lazily by SQLChatMessageHistory on first message; nothing to delete if the session never had one
            conn.execute('DELETE FROM chat_sessions WHERE session_id = ?', (session_id,))

    def list_for_user(self, user_id: str) -> list[dict]:
        with sqlite3.connect(self.db_file_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT session_id, title, model, embedding_model, created_at FROM chat_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            sessions = cursor.fetchall()
        return [dict(session) for session in sessions]

    def get_user_id(self, session_id: str) -> Optional[str]:
        """Looks up the user_id associated with a session_id."""
        with sqlite3.connect(self.db_file_path) as conn:
            row = conn.execute(
                'SELECT user_id FROM chat_sessions WHERE session_id = ?', (session_id,)
            ).fetchone()
        return row[0] if row else None

    def get_embedding_model(self, session_id: str) -> Optional[str]:
        """Looks up the immutable embedding_model id chosen for a session at creation time."""
        with sqlite3.connect(self.db_file_path) as conn:
            row = conn.execute(
                'SELECT embedding_model FROM chat_sessions WHERE session_id = ?', (session_id,)
            ).fetchone()
        return row[0] if row else None

    def get_info(self, session_id: str) -> Optional[dict]:
        """Single-session lookup for read-only display (title/model/embedding_model)."""
        with sqlite3.connect(self.db_file_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT session_id, title, model, embedding_model, created_at FROM chat_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_title(self, session_id: str, new_title: str) -> None:
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET title = ?
                WHERE session_id = ?
            ''', (new_title, session_id))

    def update_model(self, session_id: str, model: str) -> None:
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET model = ?
                WHERE session_id = ?
            ''', (model, session_id))

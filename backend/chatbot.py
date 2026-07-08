import logging
import os
import re
import json
import uuid
import sqlite3
import tools
from agent import AgentGraph, EvaluatorOutput
from tools import make_document_search_tool, make_hybrid_search_tool, make_list_documents_tool
from rag.rag_vector_db import get_embedding_model, get_persist_dir_for_embedding
from models_catalog import DEFAULT_MODEL_ID, EMBEDDING_MODEL_CATALOG, DEFAULT_EMBEDDING_MODEL_ID
from datetime import date

logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openrouter import ChatOpenRouter
from typing import Optional, Any, Dict
from langgraph.checkpoint.sqlite import SqliteSaver
import tempfile
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from dotenv import load_dotenv
load_dotenv()

os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING")
os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT")
os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

class ChatbotManager:
    def __init__(self, model_name: str = DEFAULT_MODEL_ID):
        """ starts the chatbot
        """
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_name = model_name
        self.db = "test_history.db"
        self.db_file_path = os.path.join(_root, self.db)
        self.connection_string = f"sqlite:///{self.db_file_path}"
        self._model_bundles: Dict[str, Dict[str, Any]] = {}
        self._rerank_llm = ChatOpenRouter(model=DEFAULT_MODEL_ID)
        self.tools = tools.Tools.tools[:]

        self._embedding_models = {m["id"]: get_embedding_model(m["id"]) for m in EMBEDDING_MODEL_CATALOG}
        self._embedding_persist_dirs = {m["id"]: get_persist_dir_for_embedding(m["id"]) for m in EMBEDDING_MODEL_CATALOG}
        self.embedding_model = self._embedding_models[DEFAULT_EMBEDDING_MODEL_ID]
        self._init_session_db()

        session_docs_dir = os.path.join(_root, "documents", "sessions")
        self.tools.append(make_document_search_tool(self._resolve_session_embedding))
        self.tools.append(make_hybrid_search_tool(self._resolve_session_embedding, llm=self._rerank_llm))
        self.tools.append(make_list_documents_tool(session_docs_dir=session_docs_dir))

        default_bundle = self._get_bundle(self.model_name)
        self.model = default_bundle["model"]
        self.worker_llm_with_tools = default_bundle["worker_llm_with_tools"]
        self.evaluator_llm_with_output = default_bundle["evaluator_llm_with_output"]
        self.llm_with_tools = self.worker_llm_with_tools

        self.checkpointer = MemorySaver()

        conn = sqlite3.connect(self.db, check_same_thread=False)
        sql_memory = SqliteSaver(conn)

        self._agent_graph = AgentGraph(self._get_bundle, self.tools, sql_memory)
        self.graph = self._agent_graph.graph

    def _get_bundle(self, model_id: str) -> Dict[str, Any]:
        """Builds (and caches) a {model, worker_llm_with_tools, evaluator_llm_with_output}
        bundle for the given OpenRouter model id, so each selectable model is only
        constructed once and reused across sessions/requests."""
        if model_id not in self._model_bundles:
            model = ChatOpenRouter(model=model_id)
            self._model_bundles[model_id] = {
                "model": model,
                "worker_llm_with_tools": model.bind_tools(self.tools),
                "evaluator_llm_with_output": model.with_structured_output(EvaluatorOutput),
            }
        return self._model_bundles[model_id]

    def _resolve_session_embedding(self, session_id: str):
        """Looks up which embedding model this session was created with and returns the
        matching (embedding_model_instance, persist_dir) pair. Called by the RAG tools at
        tool-call time (not at startup), since different sessions may use different models."""
        embedding_model_id = self.get_session_embedding_model(session_id) or DEFAULT_EMBEDDING_MODEL_ID
        embedding_model = self._embedding_models.get(embedding_model_id, self._embedding_models[DEFAULT_EMBEDDING_MODEL_ID])
        persist_dir = self._embedding_persist_dirs.get(embedding_model_id, self._embedding_persist_dirs[DEFAULT_EMBEDDING_MODEL_ID])
        return embedding_model, persist_dir

    def get_token_usage(self, session_id: str) -> dict:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4o-mini")
        CONTEXT_WINDOW = 128_000
        try:
            config = {"configurable": {"thread_id": session_id}}
            state = self.graph.get_state(config)
            messages = state.values.get("messages", []) if state.values else []
            used = sum(
                len(enc.encode(str(m.content)))
                for m in messages if getattr(m, "content", None)
            )
            used += 500  # system prompt overhead estimate
        except Exception:
            used = 0
        return {"used": used, "total": CONTEXT_WINDOW, "percent": round(used / CONTEXT_WINDOW * 100, 1)}

    def _init_session_db(self):
        """creates chat_sessions table in sqlite db"""

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

    def _get_session_history(self, session_id: str) -> ChatMessageHistory:
        """ gets the chat history of given session_id from sqlite database"""
        return SQLChatMessageHistory(
            session_id=session_id,
            connection=self.connection_string
        )

    def create_session(self, user_id: str, title: str, session_id: str = None,
                       model: str = None, embedding_model: str = None) -> str:
        """ creates a row in chat_sessions table."""
        session_id = session_id or str(uuid.uuid4())
        model = model or DEFAULT_MODEL_ID
        embedding_model = embedding_model or DEFAULT_EMBEDDING_MODEL_ID
        try:
            with sqlite3.connect(self.db_file_path) as conn:
                conn.execute('''
                    INSERT INTO chat_sessions (session_id, user_id, title, model, embedding_model)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, user_id, title, model, embedding_model))
            return session_id
        except Exception as e:
            logger.error("create_session failed for user %s: %s", user_id, str(e), exc_info=True)
            return f"Sorry, I encountered an error while processing your request: {e}"

    def delete_session(self, session_id: str) -> str:
        """Deletes session and its messages atomically."""
        try:
            with sqlite3.connect(self.db_file_path) as conn:
                conn.execute(
                    'DELETE FROM message_store WHERE session_id = ?', (session_id,))
                conn.execute(
                    'DELETE FROM chat_sessions WHERE session_id = ?', (session_id,))
            return session_id
        except Exception as e:
            logger.error("delete_session failed for %s: %s", session_id, str(e), exc_info=True)
            raise

    def list_sessions(self, user_id: str):

        with sqlite3.connect(self.db_file_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT session_id, title, model, embedding_model, created_at FROM chat_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            sessions = cursor.fetchall()
        return [dict(session) for session in sessions]

    def get_user_id_for_session(self, session_id: str) -> Optional[str]:
        """Looks up the user_id associated with a session_id from chat_sessions."""
        with sqlite3.connect(self.db_file_path) as conn:
            row = conn.execute(
                'SELECT user_id FROM chat_sessions WHERE session_id = ?', (session_id,)
            ).fetchone()
        return row[0] if row else None

    def get_session_embedding_model(self, session_id: str) -> Optional[str]:
        """Looks up the immutable embedding_model id chosen for a session at creation time."""
        with sqlite3.connect(self.db_file_path) as conn:
            row = conn.execute(
                'SELECT embedding_model FROM chat_sessions WHERE session_id = ?', (session_id,)
            ).fetchone()
        return row[0] if row else None

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Single-session lookup for read-only display (title/model/embedding_model), used by
        routes/pages that don't already have the full session list in context (e.g. EvaluatePage)."""
        with sqlite3.connect(self.db_file_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT session_id, title, model, embedding_model, created_at FROM chat_sessions WHERE session_id = ?',
                (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_session_title(self, session_id: str, new_title: str):
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET title = ?
                WHERE session_id = ?
            ''', (new_title, session_id))

    def update_session_model(self, session_id: str, model: str):
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET model = ?
                WHERE session_id = ?
            ''', (model, session_id))

    def get_messages(self, session_id: str):
        history = self._get_session_history(session_id)
        return history.messages

    def chat(self, session_id: str, query: str, model_id: str = None):
        """ end point method for chatting """
        response = "Sorry, I encountered an error while processing your request."
        try:
            today = date.today().strftime("%Y-%m-%d")
            message = f"Today's date: {today}.\n\nQuestion: {query}"

            result = self.graph.invoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "success_criteria": "",
                    "feedback_on_work": None,
                    "success_criteria_met": False,
                    "user_input_needed": False,
                    "tool_retry_deadline": None,
                },
                config={"configurable": {"thread_id": session_id, "model_id": model_id or DEFAULT_MODEL_ID}})
            response = result["messages"][-1].content
        except Exception as e:
            logger.error("chat failed for session %s: %s", session_id, str(e), exc_info=True)
            response = f"Sorry, I encountered an error while processing your request: {e}"
        finally:
            history = self._get_session_history(session_id)
            history.add_user_message(query)
            history.add_ai_message(response)
        return response

    def chat_stream(self, session_id: str, query: str, model_id: str = None):
        full_response = "Sorry, I encountered an error while processing your request."
        try:
            today = date.today().strftime("%Y-%m-%d")
            message = f"Today's date: {today}.\n\nQuestion: {query}"
            full_response = ""
            file_select_blocks = []
            for msg_chunk, metadata in self.graph.stream(
                {
                    "messages": [HumanMessage(content=message)],
                    "success_criteria": "",
                    "feedback_on_work": None,
                    "success_criteria_met": False,
                    "user_input_needed": False,
                    "tool_retry_deadline": None,
                },
                config={"configurable": {"thread_id": session_id, "model_id": model_id or DEFAULT_MODEL_ID}},
                stream_mode="messages"
            ):
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    full_response += msg_chunk.content
                    yield msg_chunk.content
                elif isinstance(msg_chunk, AIMessage) and msg_chunk.content and metadata.get("langgraph_node") == "timeout_notice":
                    full_response += msg_chunk.content
                    yield msg_chunk.content
                elif isinstance(msg_chunk, ToolMessage):
                    for match in re.finditer(r'```file-select\n.*?\n```', msg_chunk.content or "", re.DOTALL):
                        file_select_blocks.append(match.group(0))

            if file_select_blocks and "```file-select" not in full_response:
                extra = "\n\n" + "\n\n".join(file_select_blocks)
                yield extra
                full_response += extra
        except Exception as e:
            logger.error("chat_stream failed for session %s: %s", session_id, str(e), exc_info=True)
            full_response = f"Sorry, I encountered an error while processing your request: {e}"
            yield full_response
        finally:
            history = self._get_session_history(session_id)
            history.add_user_message(query)
            history.add_ai_message(full_response)


if __name__ == "__main__":
    manager = ChatbotManager()

    png_bytes = manager.graph.get_graph().draw_mermaid_png()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            f.write(png_bytes)
            tmp_path = f.name
    os.startfile(tmp_path)

    user = "user123"

    session_id = manager.create_session(user, "Test Tools")

    # print(manager.chat(session_id,
    #        "What is the hotel price limit in USA?"))

    # print(manager.chat(session_id,
    #         "What about south america?"))

    response1 = manager.chat(
        session_id, "I want to you list me the flights on this weekend from Munich to Madrid direct only, all airlines")
    print("1.Response: ", response1)

    response2 = manager.chat(
        session_id, "I want to see the return flights from next Monday until next Wednesday")
    print("2.Response: ", response2)
    # print(manager.chat_by_vector(session_id,
    #        "Temel gelir desteğinin faydaları özellikle hangi alanlara yönelik olmalıdır?"))

    # print(manager.chat_by_vector(session_id,
    #        "Buna ücretli iş de dahil mi?"))
    # session_id = manager.create_session("Ates Ates", "Turkish Search Test")
    # turkish_question = "Temel gelir desteği yardımlarının ana amaçları nelerdir?"
    # print(manager.chat_by_vector(session_id, turkish_question))

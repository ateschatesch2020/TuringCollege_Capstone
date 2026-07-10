import logging
import os
import re
import json
import uuid
import sqlite3
import tools
from agent import AgentGraph
from llm_bundle import LLMBundleFactory
from session_repository import SessionRepository
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


def _build_initial_state(query: str) -> Dict[str, Any]:
    """Builds the LangGraph initial state shared by chat() and chat_stream() -- the
    only difference between the two is invoke() vs. stream()."""
    today = date.today().strftime("%Y-%m-%d")
    message = f"Today's date: {today}.\n\nQuestion: {query}"
    return {
        "messages": [HumanMessage(content=message)],
        "success_criteria": "",
        "feedback_on_work": None,
        "success_criteria_met": False,
        "user_input_needed": False,
        "tool_retry_deadline": None,
    }


def _build_config(session_id: str, model_id: str = None) -> Dict[str, Any]:
    return {"configurable": {"thread_id": session_id, "model_id": model_id or DEFAULT_MODEL_ID}}


def _last_answer_content(messages: list) -> str:
    """Returns the content of the last message that isn't the evaluator's internal
    feedback commentary (tagged name="evaluator" in agent.py's evaluator node), so
    chat() returns the assistant's real answer rather than the evaluator's synthetic
    follow-up message, which is otherwise the actual last message in a completed turn."""
    for message in reversed(messages):
        if getattr(message, "name", None) != "evaluator":
            return message.content
    return messages[-1].content if messages else ""


class ChatbotManager:
    def __init__(self, model_name: str = DEFAULT_MODEL_ID, session_repo: SessionRepository = None):
        """ starts the chatbot
        """
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_name = model_name
        self.db = "test_history.db"
        self.db_file_path = os.path.join(_root, self.db)
        self.connection_string = f"sqlite:///{self.db_file_path}"
        self._rerank_llm = ChatOpenRouter(model=DEFAULT_MODEL_ID)

        self._embedding_models = {m["id"]: get_embedding_model(m["id"]) for m in EMBEDDING_MODEL_CATALOG}
        self._embedding_persist_dirs = {m["id"]: get_persist_dir_for_embedding(m["id"]) for m in EMBEDDING_MODEL_CATALOG}
        self.embedding_model = self._embedding_models[DEFAULT_EMBEDDING_MODEL_ID]
        self.session_repo = session_repo or SessionRepository(self.db_file_path)

        session_docs_dir = os.path.join(_root, "documents", "sessions")
        self.tool_registry = tools.build_tool_registry(self._resolve_session_embedding, self._rerank_llm, session_docs_dir)
        self.tools = self.tool_registry.tools

        self._llm_bundles = LLMBundleFactory(self.tools)
        default_bundle = self._llm_bundles.get(self.model_name)
        self.model = default_bundle["model"]
        self.worker_llm_with_tools = default_bundle["worker_llm_with_tools"]
        self.evaluator_llm_with_output = default_bundle["evaluator_llm_with_output"]
        self.llm_with_tools = self.worker_llm_with_tools

        self.checkpointer = MemorySaver()

        conn = sqlite3.connect(self.db_file_path, check_same_thread=False)
        sql_memory = SqliteSaver(conn)

        self._agent_graph = AgentGraph(self._llm_bundles.get, self.tools, sql_memory, self.tool_registry.routing_text)
        self.graph = self._agent_graph.graph

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
            return self.session_repo.create(session_id, user_id, title, model, embedding_model)
        except Exception as e:
            logger.error("create_session failed for user %s: %s", user_id, str(e), exc_info=True)
            return f"Sorry, I encountered an error while processing your request: {e}"

    def delete_session(self, session_id: str) -> str:
        """Deletes session and its messages atomically."""
        try:
            self.session_repo.delete(session_id)
            return session_id
        except Exception as e:
            logger.error("delete_session failed for %s: %s", session_id, str(e), exc_info=True)
            raise

    def list_sessions(self, user_id: str):
        return self.session_repo.list_for_user(user_id)

    def get_user_id_for_session(self, session_id: str) -> Optional[str]:
        """Looks up the user_id associated with a session_id from chat_sessions."""
        return self.session_repo.get_user_id(session_id)

    def get_session_embedding_model(self, session_id: str) -> Optional[str]:
        """Looks up the immutable embedding_model id chosen for a session at creation time."""
        return self.session_repo.get_embedding_model(session_id)

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Single-session lookup for read-only display (title/model/embedding_model), used by
        routes/pages that don't already have the full session list in context (e.g. EvaluatePage)."""
        return self.session_repo.get_info(session_id)

    def update_session_title(self, session_id: str, new_title: str):
        self.session_repo.update_title(session_id, new_title)

    def update_session_model(self, session_id: str, model: str):
        self.session_repo.update_model(session_id, model)

    def get_messages(self, session_id: str):
        history = self._get_session_history(session_id)
        return history.messages

    def chat(self, session_id: str, query: str, model_id: str = None):
        """ end point method for chatting """
        response = "Sorry, I encountered an error while processing your request."
        try:
            result = self.graph.invoke(_build_initial_state(query), config=_build_config(session_id, model_id))
            response = _last_answer_content(result["messages"])
        except Exception as e:
            logger.error("chat failed for session %s: %s", session_id, str(e), exc_info=True)
            response = f"Sorry, I encountered an error while processing your request: {e}"
        finally:
            self._persist_turn(session_id, query, response)
        return response

    def chat_stream(self, session_id: str, query: str, model_id: str = None):
        full_response = "Sorry, I encountered an error while processing your request."
        try:
            full_response = ""
            for chunk in self._stream_graph_events(_build_initial_state(query), _build_config(session_id, model_id)):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error("chat_stream failed for session %s: %s", session_id, str(e), exc_info=True)
            full_response = f"Sorry, I encountered an error while processing your request: {e}"
            yield full_response
        finally:
            self._persist_turn(session_id, query, full_response)

    def _stream_graph_events(self, graph_input, config: Dict[str, Any]):
        """Iterates self.graph.stream(graph_input, config, stream_mode="messages") and yields
        assistant text chunks -- the timeout-notice message, and any ```file-select``` blocks
        emitted by a tool call that the model didn't itself echo back, appended once at the
        end. Shared by chat_stream() (graph_input = a fresh turn) and retry_stream()
        (graph_input = None, resuming a forked checkpoint) so the chunk-to-text extraction
        logic can't drift between the two entry points."""
        file_select_blocks = []
        full_response = ""
        for msg_chunk, metadata in self.graph.stream(graph_input, config=config, stream_mode="messages"):
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
            yield "\n\n" + "\n\n".join(file_select_blocks)

    def _find_turn_start(self, session_id: str, turn_index: int):
        """Returns the checkpoint StateSnapshot for the turn_index-th (0-based) user turn --
        the state right after that turn's HumanMessage was merged in and before the worker
        processed it, i.e. what a graph.stream(_build_initial_state(...)) call checkpoints
        right before running "worker".

        LangGraph tags the checkpoint taken when a new invoke()/stream() input arrives with
        metadata["source"] == "input" -- but that checkpoint is the state as of the *previous*
        turn's end, one step before the new HumanMessage is actually merged in (its `next` is
        always ("__start__",)). Since the graph always edges straight from START to "worker"
        (agent.py), the checkpoint at (that input checkpoint's step + 1) is always exactly the
        one containing this turn's merged HumanMessage with `next == ("worker",)`, regardless
        of how many worker/tools/evaluator loop checkpoints follow later in the same turn."""
        config = {"configurable": {"thread_id": session_id}}
        history = list(self.graph.get_state_history(config))
        step_by_number = {snapshot.metadata["step"]: snapshot for snapshot in history}
        input_steps = sorted(
            snapshot.metadata["step"] for snapshot in history
            if snapshot.metadata.get("source") == "input"
        )
        if turn_index < 0 or turn_index >= len(input_steps):
            raise ValueError(f"No turn {turn_index} in session {session_id} ({len(input_steps)} turns exist)")
        return step_by_number[input_steps[turn_index] + 1]

    def retry_stream(self, session_id: str, turn_index: int, new_query: str, model_id: str = None):
        """Edits the turn_index-th user message and regenerates from there by forking the
        checkpoint history instead of replaying it -- turns after turn_index are simply not
        part of the new branch, so they're never sent to the model, and nothing in the old
        branch is deleted.

        Locating/forking the checkpoint happens outside the try/finally below on purpose: if
        it fails (e.g. this session predates checkpoint-backed history), nothing has been
        truncated yet, so there's no new "turn" to persist -- persisting one anyway would
        append a bogus trailing message_store row instead of actually discarding anything,
        breaking the "editing turn N discards everything after it" invariant."""
        snapshot = self._find_turn_start(session_id, turn_index)
        old_human = next(m for m in reversed(snapshot.values["messages"]) if isinstance(m, HumanMessage))
        today = date.today().strftime("%Y-%m-%d")
        edited_message = HumanMessage(content=f"Today's date: {today}.\n\nQuestion: {new_query}", id=old_human.id)
        forked_config = self.graph.update_state(snapshot.config, {"messages": [edited_message]})
        forked_config["configurable"]["model_id"] = model_id or DEFAULT_MODEL_ID

        self.session_repo.truncate_messages(session_id, keep_count=turn_index * 2)

        full_response = "Sorry, I encountered an error while processing your request."
        try:
            full_response = ""
            for chunk in self._stream_graph_events(None, forked_config):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error("retry_stream failed for session %s turn %s: %s", session_id, turn_index, str(e), exc_info=True)
            full_response = f"Sorry, I encountered an error while processing your request: {e}"
            yield full_response
        finally:
            self._persist_turn(session_id, new_query, full_response)

    def _persist_turn(self, session_id: str, query: str, response: str) -> None:
        history = self._get_session_history(session_id)
        history.add_user_message(query)
        history.add_ai_message(response)


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

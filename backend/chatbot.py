import logging
import os
import re
import faiss
import numpy as np
import json
import uuid
import sqlite3
import tools
from tools import make_document_search_tool, make_hybrid_search_tool
from datetime import date, datetime

logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openrouter import ChatOpenRouter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

from langchain_protocol import Annotated
from langgraph.graph import END, START, StateGraph, add_messages
from typing import TypedDict, Optional, List, Any, Dict
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver
import tempfile
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

os.environ["LANGSMITH_TRACING"] = os.getenv("LANGSMITH_TRACING")
os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT")
os.environ["LANGSMITH_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool

class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )

class ChatbotManager:
    def __init__(self, model_name: str = "openai/gpt-4o-mini"):
        """ starts the chatbot
        """
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_name = model_name
        self.db = "test_history.db"
        self.db_file_path = os.path.join(_root, self.db)
        self.connection_string = f"sqlite:///{self.db_file_path}"
        self.model = ChatOpenRouter(
            model=self.model_name)
        self.tools = tools.Tools.tools[:]

        # self.embedding_model = HuggingFaceEmbeddings(
        #   model="sentence-transformers/all-MiniLM-L6-v2")
        self.embedding_model = OpenAIEmbeddings(
            #model="openai/text-embedding-3-small",
            model="openai/text-embedding-3-small",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"))
        self._init_session_db()

        sessions_dir = os.path.join(_root, "chroma_db", "sessions")
        self.tools.append(make_document_search_tool(
            embedding_model=self.embedding_model,
            sessions_dir=sessions_dir,
        ))
        self.tools.append(make_hybrid_search_tool(
            embedding_model=self.embedding_model,
            llm=self.model,
            sessions_dir=sessions_dir,
        ))
        self.llm_with_tools = self.model.bind_tools(self.tools)

        worker_llm = self.model
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)
        evaluator_llm = self.model
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        
        self.checkpointer = MemorySaver()

        self.agent_prompt = """
        You are an Office Helper assistant. Help users work with their company documents and create professional outputs.
        You have tools to search uploaded documents, search the web, and generate presentations, Word documents, and PDF files.

        CRITICAL RULES:
        - For ANY question about uploaded documents, ALWAYS use the search_documents tool first before answering.
        - For current information not available in uploaded documents, use web_search.
        - When the user requests a presentation, Word document, or PDF file, use the appropriate generation tool and include the download link in your response.
        - For checklists, comparison tables, or price lists shown in chat, generate them as formatted markdown — no file tool needed unless the user asks for a downloadable file.
        - NEVER invent document content. Only use what search_documents returns.
        - Reply in the user's language.
        """

        graph_builder = StateGraph(State)

        def chatbot(state: State):
            print(state)
            return {"messages" : [self.llm_with_tools.invoke(state["messages"])]}

        graph_builder.add_edge(START, "worker")

          # Add nodes
        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools, handle_tool_errors=True))
        graph_builder.add_node("evaluator", self.evaluator)

        # Add edges
        graph_builder.add_conditional_edges(
            "worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END}
        )
        
        conn = sqlite3.connect(self.db, check_same_thread=False)
        sql_memory = SqliteSaver(conn)

        self.graph = graph_builder.compile(checkpointer=sql_memory)

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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def _get_session_history(self, session_id: str) -> ChatMessageHistory:
        """ gets the chat history of given session_id from sqlite database"""
        return SQLChatMessageHistory(
            session_id=session_id,
            connection=self.connection_string
        )

    def create_session(self, user_id: str, title: str, session_id: str = None) -> str:
        """ creates a row in chat_sessions table."""
        session_id = session_id or str(uuid.uuid4())
        try:
            with sqlite3.connect(self.db_file_path) as conn:
                conn.execute('''
                    INSERT INTO chat_sessions (session_id, user_id, title)
                    VALUES (?, ?, ?)
                ''', (session_id, user_id, title))
            return session_id
        except Exception as e:
            logger.error("create_session failed for user %s", user_id, exc_info=True)
            return "Sorry, I encountered an error while processing your request."

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
            logger.error("delete_session failed for %s", session_id, exc_info=True)
            raise

    def list_sessions(self, user_id: str):

        with sqlite3.connect(self.db_file_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT session_id, title, created_at FROM chat_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            sessions = cursor.fetchall()
        return [dict(session) for session in sessions]

    def update_session_title(self, session_id: str, new_title: str):
        with sqlite3.connect(self.db_file_path) as conn:
            conn.execute('''
                UPDATE chat_sessions
                SET title = ?
                WHERE session_id = ?
            ''', (new_title, session_id))

    def get_messages(self, session_id: str):
        history = self._get_session_history(session_id)
        return history.messages

    def chat(self, session_id: str, query: str):
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
                },
                config={"configurable": {"thread_id": session_id}})
            response = result["messages"][-1].content
        except Exception as e:
            logger.error("chat failed for session %s", session_id, exc_info=True)
        finally:
            history = self._get_session_history(session_id)
            history.add_user_message(query)
            history.add_ai_message(response)
        return response

    def chat_stream(self, session_id: str, query: str):
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
                },
                config={"configurable": {"thread_id": session_id}},
                stream_mode="messages"
            ):
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
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
            logger.error("chat_stream failed for session %s", session_id, exc_info=True)
            full_response = "Sorry, I encountered an error while processing your request."
            yield full_response
        finally:
            history = self._get_session_history(session_id)
            history.add_user_message(query)
            history.add_ai_message(full_response)

    def embed(self, text):
        response = self.embedding_model.embed_query(text)
        k = 2
        index = faiss.IndexFlatL2(1536)
        distances, indices = index.search(
            np.array([response]), k
        )
        return response

    def invoke_with_user(self, user_id: str, question: str):
        thread_id = f"user_session_{user_id}"
        return self.myagent.invoke({
            "messages": [HumanMessage(content=question)]},
            config={"configurable": {"thread_id": thread_id}}
        )

    def _close_orphaned_tool_calls(self, messages: List[Any]) -> List[Any]:
        """Inserts a placeholder ToolMessage for any tool_call left unanswered
        (e.g. by a prior run that crashed mid tool-execution), so the message
        history is always valid before it's sent to the LLM provider."""
        fixed = []
        for i, message in enumerate(messages):
            fixed.append(message)
            if not (isinstance(message, AIMessage) and message.tool_calls):
                continue
            pending = {tc["id"] for tc in message.tool_calls}
            for next_msg in messages[i + 1:]:
                if isinstance(next_msg, ToolMessage):
                    pending.discard(next_msg.tool_call_id)
                else:
                    break
            for tool_call_id in pending:
                fixed.append(ToolMessage(
                    content="Tool call was interrupted before it could complete.",
                    tool_call_id=tool_call_id,
                    status="error",
                ))
        return fixed

    def worker(self, state: State) -> Dict[str, Any]:
        system_message = f"""You are an Office Helper assistant. Help users work with their company documents and create professional outputs.
        The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.

        TOOL ROUTING — choose the right tool for each request:

        • search_documents: Use for ANY question, summary, extraction, or analysis related to uploaded documents.
          - User asks a question → always call search_documents first before answering.
          - User wants a summary, key points, or specific info from a document → search_documents.
          - User wants to create a presentation, report, or document based on uploaded content → search_documents first, then generate the file.
          - NEVER answer document-related questions from memory — only use what search_documents returns.

        • hybrid_search_documents: A more thorough alternative to search_documents — runs semantic and keyword
          search separately, merges the results, and re-ranks them with an LLM before returning the top 5 chunks.
          - Use it when search_documents doesn't return enough relevant information.
          - Use it when the query needs precise keyword matches (exact names, codes, numbers) alongside semantic matching.

        • web_search: Use when the question requires current, real-time, or up-to-date information that cannot be in uploaded documents.
          - News, prices, weather, live schedules, recent events → web_search.
          - Do NOT use web_search for questions that can be answered from uploaded documents.

        • generate_presentation / generate_word_document / generate_pdf_document: Use when the user explicitly asks for a downloadable file.
          - Always include the download link in your response.
          - For lists, tables, or summaries shown inline in chat, use formatted markdown — no file tool needed unless a download is requested.

        Reply in the user's language.

        This is the success criteria:
        {state["success_criteria"]}
        You should reply either with a question for the user about this assignment, or with your final response.
        If you have a question for the user, you need to reply by clearly stating your question. An example might be:

        Question: please clarify whether you want a summary or a detailed answer

        If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
        """

        if state.get("feedback_on_work"):
            system_message += f"""
        Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
        Here is the feedback on why this was rejected:
        {state["feedback_on_work"]}
        With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""

        # Add in the system message

        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True

        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages

        messages = self._close_orphaned_tool_calls(messages)

        # Invoke the LLM with tools
        response = self.worker_llm_with_tools.invoke(messages)

        # Return updated state
        return {
            "messages": [response],
        }
    
        # it decides whether worker should use a tool or not
    
    def worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        else:
            return "evaluator"
        
    def format_conversation(self, messages: List[Any]) -> str:
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation

    def evaluator(self, state: State) -> State:
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
        Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
        and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

        The entire conversation with the assistant, with the user's original request and all replies, is:
        {self.format_conversation(state["messages"])}

        The success criteria for this assignment is:
        {state["success_criteria"]}

        And the final response from the Assistant that you are evaluating is:
        {last_response}

        Respond with your feedback, and decide if the success criteria is met by this response.
        Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

        The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
        Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

        """
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        evaluator_messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ]

        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
        new_state = {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {eval_result.feedback}",
                }
            ],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }
        return new_state

    def route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        else:
            return "worker"


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

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_protocol import Annotated
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from models_catalog import DEFAULT_MODEL_ID


class State(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool
    tool_retry_deadline: Optional[float]
    tool_retry_timeout_seconds: int


class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(
        description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
    )


def _close_orphaned_tool_calls(messages: List[Any]) -> List[Any]:
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


def _format_conversation(messages: List[Any]) -> str:
    conversation = "Conversation history:\n\n"
    for message in messages:
        if isinstance(message, HumanMessage):
            conversation += f"User: {message.content}\n"
        elif isinstance(message, AIMessage):
            text = message.content or "[Tools use]"
            conversation += f"Assistant: {text}\n"
    return conversation


class AgentGraph:
    """Builds and owns the LangGraph worker/tools/evaluator/timeout_notice graph.

    get_bundle(model_id) resolves the {model, worker_llm_with_tools,
    evaluator_llm_with_output} bundle for a given OpenRouter model id; tools/
    checkpointer are the LangGraph tool list and checkpointer to compile against.
    """

    def __init__(self, get_bundle, tools: list, checkpointer):
        self._get_bundle = get_bundle

        graph_builder = StateGraph(State)
        graph_builder.add_edge(START, "worker")
        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=tools, handle_tool_errors=True))
        graph_builder.add_node("evaluator", self.evaluator)
        graph_builder.add_node("timeout_notice", self.timeout_notice)
        graph_builder.add_conditional_edges(
            "worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator", "timeout": "timeout_notice"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_edge("timeout_notice", END)
        graph_builder.add_conditional_edges(
            "evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END}
        )

        self.graph = graph_builder.compile(checkpointer=checkpointer)

    def worker(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        model_id = config.get("configurable", {}).get("model_id", DEFAULT_MODEL_ID)
        worker_llm_with_tools = self._get_bundle(model_id)["worker_llm_with_tools"]
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

        • list_uploaded_documents: Use to answer "how many documents are uploaded" or "what are their names" questions,
          and to look up a document's exact filename before using it as the document_name filter on
          search_documents/hybrid_search_documents.

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

        messages = _close_orphaned_tool_calls(messages)

        # Invoke the LLM with tools
        response = worker_llm_with_tools.invoke(messages)

        # Establish (or carry forward) the deadline for this turn's tool-retry loop
        timeout_seconds = state.get("tool_retry_timeout_seconds", 30)
        deadline = state.get("tool_retry_deadline") or (time.time() + timeout_seconds)

        # Return updated state
        return {
            "messages": [response],
            "tool_retry_deadline": deadline,
            "tool_retry_timeout_seconds": timeout_seconds,
        }

        # it decides whether worker should use a tool or not

    def worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            deadline = state.get("tool_retry_deadline")
            if deadline and time.time() > deadline:
                return "timeout"
            return "tools"
        else:
            return "evaluator"

    def timeout_notice(self, state: State, config: RunnableConfig) -> Dict[str, Any]:
        model_id = config.get("configurable", {}).get("model_id", DEFAULT_MODEL_ID)
        model = self._get_bundle(model_id)["model"]
        last_error = "unknown error"
        for message in reversed(state["messages"]):
            if isinstance(message, ToolMessage) and str(message.content).startswith("Error:"):
                last_error = message.content
                break

        timeout_seconds = state.get("tool_retry_timeout_seconds", 30)
        next_timeout_seconds = timeout_seconds * 2

        explain_prompt = [
            SystemMessage(content=(
                "You explain tool failures to end users in simple, friendly, non-technical "
                "language. Reply in the same language the user has been using in this conversation."
            )),
            HumanMessage(content=(
                f"A tool call was retried automatically for {timeout_seconds} seconds without "
                f"succeeding, so the assistant stopped trying to avoid wasting more time. "
                f"The underlying error was: {last_error}\n\n"
                f"Write a short message to the user that:\n"
                f"1. Explains the operation took too long ({timeout_seconds}s) and was stopped.\n"
                f"2. Briefly explains, in plain terms, what went wrong (translate the technical error).\n"
                f"3. Asks whether they'd like you to keep trying for longer (about {next_timeout_seconds}s), "
                f"or would rather try a different approach given the error."
            )),
        ]
        response = model.invoke(explain_prompt)

        return {
            "messages": [response],
            "user_input_needed": True,
            "success_criteria_met": False,
            "tool_retry_timeout_seconds": next_timeout_seconds,
        }

    def evaluator(self, state: State, config: RunnableConfig) -> State:
        model_id = config.get("configurable", {}).get("model_id", DEFAULT_MODEL_ID)
        evaluator_llm_with_output = self._get_bundle(model_id)["evaluator_llm_with_output"]
        last_response = state["messages"][-1].content

        system_message = """You are an evaluator that determines if a task has been completed successfully by an Assistant.
        Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
        and whether more input is needed from the user."""

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

        The entire conversation with the assistant, with the user's original request and all replies, is:
        {_format_conversation(state["messages"])}

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

        eval_result = evaluator_llm_with_output.invoke(evaluator_messages)
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

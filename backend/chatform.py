import logging
import os
import re
import uuid
import tools
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode
from langchain_openrouter import ChatOpenRouter
from langchain_protocol import Annotated
from typing import TypedDict, Optional, List, Any, Dict
from pydantic import BaseModel, Field


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
        description="True if more input is needed from the user, or the assistant is stuck"
    )


class FormManager:
    def __init__(self, model_name: str = "openai/gpt-4o-mini"):
        self.model = ChatOpenRouter(model=model_name)
        self.form_tools = tools.Tools.form_tools[:]
        self.worker_llm_with_tools = self.model.bind_tools(self.form_tools)
        self.evaluator_llm_with_output = self.model.with_structured_output(EvaluatorOutput)

        graph_builder = StateGraph(State)
        graph_builder.add_edge(START, "worker")
        graph_builder.add_node("worker", self.formWorker)
        graph_builder.add_node("tools", ToolNode(tools=self.form_tools, handle_tool_errors=True))
        graph_builder.add_node("evaluator", self.formEvaluator)
        graph_builder.add_conditional_edges(
            "worker", self._worker_router, {"tools": "tools", "evaluator": "evaluator"}
        )
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges(
            "evaluator", self._route_based_on_evaluation, {"worker": "worker", "END": END}
        )
        self.graph = graph_builder.compile(checkpointer=MemorySaver())

    def formWorker(self, state: State) -> Dict[str, Any]:
        system_message = """You are a file search assistant. Your only job is to find files on disk using the available tools.
The user message will contain a keyword and a search mode. Use the tool that matches the mode:
- mode "exact"    → find_files_by_name_exact(filename=keyword)
- mode "contains" → find_files_by_name_contains(keyword=keyword)
- mode "both"     → call both find_files_by_name_exact AND find_files_by_name_contains
- mode "project"  → search_project_files(project_name=keyword, query=keyword)
Always call the tool(s) — do not answer without searching first."""

        messages = state["messages"]
        found_system = False
        for msg in messages:
            if isinstance(msg, SystemMessage):
                msg.content = system_message
                found_system = True
        if not found_system:
            messages = [SystemMessage(content=system_message)] + messages

        response = self.worker_llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def formEvaluator(self, state: State) -> Dict[str, Any]:
        last_response = state["messages"][-1].content
        system_message = (
            "Evaluate if files were found. "
            "If the response lists file paths or folder names, set success_criteria_met=True. "
            "If it says no files found or no folder found, set success_criteria_met=False and user_input_needed=True."
        )
        user_message = f"Response: {last_response}\nCriteria: {state['success_criteria']}"
        if state.get("feedback_on_work"):
            user_message += f"\nPrevious feedback: {state['feedback_on_work']}"

        eval_result = self.evaluator_llm_with_output.invoke([
            SystemMessage(content=system_message),
            HumanMessage(content=user_message),
        ])
        return {
            "messages": [{"role": "assistant", "content": f"Evaluator: {eval_result.feedback}"}],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed,
        }

    def _worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "evaluator"

    def _route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        return "worker"

    def search(self, keyword: str, exact: bool, contains: bool) -> str:
        mode = "both" if exact and contains else ("exact" if exact else "contains")
        msg = f"mode: {mode}. keyword: {keyword}"
        thread_id = str(uuid.uuid4())
        result = self.graph.invoke(
            {
                "messages": [HumanMessage(content=msg)],
                "success_criteria": "Files must be found and listed with their paths.",
                "feedback_on_work": None,
                "success_criteria_met": False,
                "user_input_needed": False,
            },
            {"configurable": {"thread_id": thread_id}},
        )

        # Extract tool outputs — authoritative source of file listings and file-select blocks
        tool_texts = []
        file_select_blocks = []
        for message in result["messages"]:
            if not isinstance(message, ToolMessage):
                continue
            content = message.content if isinstance(message.content, str) else str(message.content)
            block_match = re.search(r"```file-select\n.*?\n```", content, re.DOTALL)
            if block_match:
                file_select_blocks.append(block_match.group(0))
                content = content[: block_match.start()].strip()
            if content:
                tool_texts.append(content)

        combined = "\n\n".join(tool_texts)
        if file_select_blocks:
            combined += ("\n\n" if combined else "") + "\n\n".join(file_select_blocks)

        return combined.strip() or "No files found."

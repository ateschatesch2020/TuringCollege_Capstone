from typing import Any, Dict

from langchain_openrouter import ChatOpenRouter

from agent import EvaluatorOutput


class LLMBundleFactory:
    """Builds and caches a {model, worker_llm_with_tools, evaluator_llm_with_output}
    bundle per OpenRouter model id, so each selectable model is only constructed once
    and reused across sessions/requests. Extracted from ChatbotManager._get_bundle so
    LLM-client construction/caching isn't mixed into the session/graph orchestration.

    tools is the list this factory's bundles will be bound to; ChatbotManager passes
    its own self.tools list by reference, so tools appended after this factory is
    constructed are still picked up (bundles are only actually built lazily, on the
    first get() call for a given model id)."""

    def __init__(self, tools: list):
        self._tools = tools
        self._bundles: Dict[str, Dict[str, Any]] = {}

    def get(self, model_id: str) -> Dict[str, Any]:
        if model_id not in self._bundles:
            model = ChatOpenRouter(model=model_id)
            self._bundles[model_id] = {
                "model": model,
                "worker_llm_with_tools": model.bind_tools(self._tools),
                "evaluator_llm_with_output": model.with_structured_output(EvaluatorOutput),
            }
        return self._bundles[model_id]

import deepeval
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
import os


deepeval.login("confident_us_mi2F9Prqn81UJrqywO7sqM+pR7W7LS5MepLi4LBtbeE=")

from deepeval.test_case import LLMTestCase
from deepeval.metrics import ContextualPrecisionMetric

contextual_precision_metrics = ContextualPrecisionMetric()

test_case = LLMTestCase(
    input="Who is the current president of USA in 2024",
    # Should come from an LLM or from an Agent or RAG
    actual_output="Donald Trump",
    # RAG - Vector DB, AI Agent - Agent Tools, LLM - LLM invoke response
    retrieval_context=["Donald Trump serves as the current president of America."],
    expected_output="Donald Trump is the current president of America."
)

contextual_precision_metrics.measure(test_case=test_case)


if __name__ == "__main__" :

    print("-" *50)
    print("score:")
    print(contextual_precision_metrics.score)
    print("success:")
    print(contextual_precision_metrics.success)
    print("score_breakdown:")
    print(contextual_precision_metrics.score_breakdown)
    print("-" *50)


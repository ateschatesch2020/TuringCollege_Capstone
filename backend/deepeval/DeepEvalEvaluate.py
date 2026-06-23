import deepeval
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()
import os


deepeval.login("confident_us_mi2F9Prqn81UJrqywO7sqM+pR7W7LS5MepLi4LBtbeE=")

from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.evaluate import evaluate


answer_relevancy_metric = AnswerRelevancyMetric()
test_case = LLMTestCase(
  input="Who is the current president of the United States of America?",
  actual_output="Joe Biden",
  retrieval_context=["Joe Biden serves as the current president of America."]
)


if __name__ == "__main__" :

    print("-" *50)
    print(evaluate(test_cases=[test_case], metrics=[answer_relevancy_metric]))
    print("-" *50)


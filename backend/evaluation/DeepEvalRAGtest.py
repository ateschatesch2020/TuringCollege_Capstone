from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os
load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

embedding_model  = OpenAIEmbeddings(
    model="openai/text-embedding-3-small",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"))

persist_directory = os.path.join(_ROOT, "chroma_db")

vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embedding_model
)


if __name__ == "__main__" :
    question = "ABD'de gunluk hotel konaklama fiyati limiti nedir?"
    results = vectorstore.similarity_search_with_score(question, k=2)

    from deepeval.test_case import LLMTestCase
    from deepeval.dataset import EvaluationDataset

    test_case = LLMTestCase(
        input=question,
        actual_output=results[0][0].page_content,
        expected_output="200 euro" )

    dataset = EvaluationDataset()
    dataset.add_test_case(test_case=test_case)

    from deepeval.test_case import LLMTestCaseParams
    from deepeval.metrics import GEval

    concise_metrics = GEval(
        name = "Concise",
        criteria="Assess if the actual output remains concise while preserving all essential information.",
        
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT
        ]
    )

    from deepeval.test_case import LLMTestCaseParams
    from deepeval.metrics import GEval

    completness_metrics = GEval(
        name = "Completeness",
        criteria="Assess whether the actual output retains all the key information from the input",
        
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT
        ]
    )

    from deepeval.evaluate import evaluate
    from deepeval.metrics import AnswerRelevancyMetric

    evaluate(dataset.test_cases, metrics=[
        completness_metrics, 
        AnswerRelevancyMetric(),
        concise_metrics
    ])

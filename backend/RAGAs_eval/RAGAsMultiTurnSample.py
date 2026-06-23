import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import ContextRecall, NoiseSensitivity
from dotenv import load_dotenv
load_dotenv()

#response = the output of the system
#reference = expected output
#retrieved_contexts = the chunks retrieved

test_case = [{
    "user_input":"Where is the Eiffel Tower located?",
    "response": "Paris",
    "retrieved_contexts":["Paris is the capital of France."],
    "reference":"The Eiffel Tower is located in Paris."
},
   {"user_input":"What is MCP",
    "response": """
        MCP (Model Context Protocol) is designed to enhance AI application development
        by integrating context and function calling. It builds upon the existing method
        of API calls from large language models (LLMs) to simplify and standardize development processes. Unlike a simple replacement for previous integration methods, MCP connects AI applications to contextual information, making development more straightforward and consistent. Security considerations include OAuth implementation with HTTP+SSE transport, which carries typical risks associated with standard OAuth flows.
    """,
    "reference": """
    Model Context Protocol (MCP) is a client-server protocol designed to connect AI applications with context and external APIs, inspired by the Language Server Protocol (LSP). It allows AI apps to retrieve information from various sources, including messaging apps and GitHub repositories, making development simpler and more consistent. MCP supports a wide range of actions and can be implemented by any AI application, not just those using OpenAI's models. The protocol includes reference servers, official integrations, and community-developed servers, demonstrating its flexibility and broad applicability in the AI ecosystem.
    """,
    "retrieved_contexts":["""
                          The Model Context Protocol (MCP) is an open standard designed to streamline the integration of AI models with various data sources and tools. It functions similarly to how USB-C provides a universal connection for devices, offering a standardized method for AI applications to access and interact with diverse datasets and services
                          """]
   }
]

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
context_recall = ContextRecall(llm=evaluator_llm)
noise_sensitivity = NoiseSensitivity(llm=evaluator_llm)

context_recall_inputs = [
    {"user_input": row["user_input"], "retrieved_contexts": row["retrieved_contexts"], "reference": row["reference"]}
    for row in test_case
]
noise_sensitivity_inputs = [
    {"user_input": row["user_input"], "response": row["response"], "reference": row["reference"], "retrieved_contexts": row["retrieved_contexts"]}
    for row in test_case
]

#context recall = claims in the reference supported by the retrieved context
# / total claims
if __name__ == "__main__":
   print("-" * 50)
   print(f"Context Recall Scores: ")
   print([r.value for r in asyncio.run(context_recall.abatch_score(context_recall_inputs))])
   print(f"Noise Sensitivity Scores: ")
   print([r.value for r in asyncio.run(noise_sensitivity.abatch_score(noise_sensitivity_inputs))])
   print("-" * 50)

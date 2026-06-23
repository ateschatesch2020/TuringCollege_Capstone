import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import NoiseSensitivity
from dotenv import load_dotenv
load_dotenv()

user_input = "What is MCP"

response = """
    MCP (Model Context Protocol) is designed to enhance AI application development
    by integrating context and function calling. It builds upon the existing method
    of API calls from large language models (LLMs) to simplify and standardize
    development processes. Unlike a simple replacement
    for previous integration methods, MCP connects AI applications to contextual
    information, making development more straightforward and consistent. Security
      considerations include OAuth implementation with HTTP+SSE transport, which
      carries typical risks associated with standard OAuth flows.
"""
reference = """
Model Context Protocol (MCP) is a client-server protocol designed to connect AI
applications with context and external APIs, inspired by the Language Server Protocol
  (LSP). It allows AI apps to retrieve information from various sources, including
  messaging apps and GitHub repositories, making development simpler and more
  consistent. MCP supports a wide range of actions and can be implemented by any
  AI application, not just those using OpenAI's models. The protocol includes
  reference servers, official integrations, and community-developed servers,
  demonstrating its flexibility and broad applicability in the AI ecosystem.
"""

retrieved_contexts = ["""
                      The Model Context Protocol (MCP) is an open standard designed
                    to streamline the integration of AI models with various data
                    sources and tools. It functions similarly to how USB-C provides
                    a universal connection for devices, offering a standardized
                    method for AI applications to access and interact with diverse
                    datasets and services
                      """]

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
noice_sentitivity = NoiseSensitivity(llm=evaluator_llm)
#noise sensitivity = total incorrect claims / total claims
if __name__ == "__main__":
   print("-" * 50)
   print(f"Noise Sensitivity Score: ")
   print(asyncio.run(noice_sentitivity.ascore(
       user_input=user_input,
       response=response,
       reference=reference,
       retrieved_contexts=retrieved_contexts,
   )).value)
   print("-" * 50)

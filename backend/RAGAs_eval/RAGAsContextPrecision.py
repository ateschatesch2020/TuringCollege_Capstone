import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import ContextPrecision
from dotenv import load_dotenv
load_dotenv()

#response = the output of the system
#reference = expected output
#retrieved_contexts = the chunks retrieved

user_input = "Where is the Eiffel Tower located?"
reference = "The Eiffel Tower is located in Paris."
retrieved_contexts = [
    "The Eiffel Tower is located in Paris.",
    "The Brandenburg Gate is located in Berlin."
]

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
context_precision = ContextPrecision(llm=evaluator_llm)
#context precision = true@k / total

if __name__ == "__main__":
   print("-" * 50)
   print(f"Context Precision Score: ")
   print(asyncio.run(context_precision.ascore(
       user_input=user_input,
       reference=reference,
       retrieved_contexts=retrieved_contexts,
   )).value)
   print("-" * 50)

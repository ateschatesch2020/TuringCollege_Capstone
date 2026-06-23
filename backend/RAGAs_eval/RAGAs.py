import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import ContextRecall
from dotenv import load_dotenv
load_dotenv()

#response = the output of the system
#reference = expected output
#retrieved_contexts = the chunks retrieved

user_input = "Where is the Eiffel Tower located?"
retrieved_contexts = ["Paris is the capital of France."]
reference = "The Eiffel Tower is located in Paris."

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
context_recall = ContextRecall(llm=evaluator_llm)
#context recall = claims in the reference supported by the retrieved context
# / total claims
if __name__ == "__main__":
   print("-" * 50)
   print(f"Context Recall Score: ")
   print(asyncio.run(context_recall.ascore(
       user_input=user_input,
       retrieved_contexts=retrieved_contexts,
       reference=reference,
   )).value)
   print("-" * 50)

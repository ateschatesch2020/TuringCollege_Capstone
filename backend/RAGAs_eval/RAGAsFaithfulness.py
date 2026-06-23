import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness
from dotenv import load_dotenv
load_dotenv()

#response = the output of the system
#reference = expected output
#retrieved_contexts = the chunks retrieved

user_input = "When was the first super bowl?"
response = "The first superbowl was held on Jan 15, 1967"
retrieved_contexts = [
    "The First AFL–NFL World Championship Game was an American football game played on January 15, 1967, at the Los Angeles Memorial Coliseum in Los Angeles."
]

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
faithfulness = Faithfulness(llm=evaluator_llm)
#context recall = claims in the reference supported by the retrieved context
# / total claims
if __name__ == "__main__":
   print("-" * 50)
   print(f"Faithfulness Score: ")
   print(asyncio.run(faithfulness.ascore(
       user_input=user_input,
       response=response,
       retrieved_contexts=retrieved_contexts,
   )).value)
   print("-" * 50)

import os
import asyncio
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.embeddings import OpenAIEmbeddings as RagasOpenAIEmbeddings
from ragas.metrics.collections import AnswerRelevancy
from dotenv import load_dotenv
load_dotenv()

#response = the output of the system
#reference = expected output
#retrieved_contexts = the chunks retrieved

user_input = "Where is the Eiffel Tower located?"
response = "Paris"

client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
evaluator_llm = llm_factory("openai/gpt-4o-mini", client=client)
evaluator_embeddings = RagasOpenAIEmbeddings(client=client, 
                                             model="openai/text-embedding-3-small")

answer_relevancy = AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings)
#context recall = claims in the reference supported by the retrieved context
# / total claims
if __name__ == "__main__":
   print("-" * 50)
   print(f"Response relevancy Score: ")
   print(asyncio.run(answer_relevancy.ascore(user_input=user_input, response=response)).value)
   print("-" * 50)

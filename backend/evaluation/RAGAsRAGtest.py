import sys
import types

vertexai_chat_module = types.ModuleType("langchain_community.chat_models.vertexai")
vertexai_chat_module.ChatVertexAI = type("ChatVertexAI", (), {})
sys.modules["langchain_community.chat_models.vertexai"] = vertexai_chat_module

vertexai_llm_module = types.ModuleType("langchain_community.llms.vertexai")
vertexai_llm_module.VertexAI = type("VertexAI", (), {})
sys.modules["langchain_community.llms.vertexai"] = vertexai_llm_module

#from langchain_ollama import OllamaEmbeddings
#from langchain_chroma import Chroma
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document
#from langchain_ollama import ChatOllama
from openai import AsyncOpenAI
from dotenv import load_dotenv
from langchain_chroma import Chroma

load_dotenv()
import os

llm = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


# Create a retriever
retriever = vectordb.as_retriever()

def format_docs(docs: List[Document]) -> str:
    return "\n\n".join([d.page_content for d in docs])


template = """Answer the question based only on the following context:

    {context}
    
    Give a summary not the full detail

    Question: {question}
    """
prompt = ChatPromptTemplate.from_template(template)


def retrieve_and_format(question):
    docs = retriever.invoke(question)
    return format_docs(docs)

chain = {"context": retrieve_and_format, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser()

response = chain.invoke("What is MCP")

print(response)

from langchain_classic.chains import RetrievalQA

qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

def query_with_context(question):
    retrieved_document = retrieve_and_format(question)
    response = qa_chain.run(question)
    return response, retrieved_document

actual, context = query_with_context("What is MCP")

test_data = [
    {
        "input": "What is MCP",
        "reference": "The Model Context Protocol (MCP) addresses this challenge by providing a standardized way for LLMs to connect with external data sources and tools—essentially a “universal remote” for AI apps. Released by Anthropic as an open-source protocol, MCP builds on existing function calling by eliminating the need for custom integration between LLMs and other apps."
    },
    {
        "input": "What is Relationship between function calling & Model Context Protocol",
        "reference": "The Model Context Protocol (MCP) builds on top of function calling, a well-established feature that allows large language models (LLMs) to invoke predetermined functions based on user requests. MCP simplifies and standardizes the development process by connecting AI applications to context while leveraging function calling to make API interactions more consistent across different applications and model vendors."
    },
    {
        "input": "What are the core components of MCP, just give the heading",
        "reference":""" 
                    - MCP Client
                    - MCP Servers
                    - Protocol Handshake
                    - Capability Discovery
                """
    }
]

dataset = []

for question in test_data:
    actual, context = query_with_context(question['input'])
    
    dataset.append({
        "user_input": question['input'],
        "retrieved_contexts": [context],
        "response": actual,
        "reference": question['reference']
    })

if __name__ == "__main__":

    from ragas.metrics import LLMContextRecall, NoiseSensitivity, Faithfulness, FactualCorrectness, AnswerRelevancy
    from ragas.llms import LangchainLLMWrapper
    from ragas import (EvaluationDataset, evaluate)

    print("-" *50)
    evaluator_llm = LangchainLLMWrapper(llm)

    evaluation_dataset = EvaluationDataset.from_list(dataset)

    result = evaluate(dataset=evaluation_dataset, 
                    metrics=[LLMContextRecall(),
                            Faithfulness(),
                            AnswerRelevancy(),
                            FactualCorrectness()],
                    llm = evaluator_llm)
    print(result)
    print(result.to_pandas)
    print("-" *50)

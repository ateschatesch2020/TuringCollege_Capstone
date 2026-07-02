import asyncio
import json
import os
import re

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI

load_dotenv()

from .rag_vector_db import _get_embedding_model, _load_pdf


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )


async def _llm_score(llm: ChatOpenAI, prompt: str) -> float:
    response = await llm.ainvoke(prompt + "\n\nRespond with only a decimal number between 0 and 1, nothing else.")
    text = response.content.strip()
    match = re.search(r"1(?:\.0+)?|0(?:\.\d+)?|\.\d+", text)
    return min(1.0, max(0.0, float(match.group()))) if match else 0.0


async def _score_faithfulness(llm: ChatOpenAI, question: str, answer: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Context:\n{ctx}\n\n"
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        "Rate how faithfully the answer is supported by the context alone (ignore prior knowledge). "
        "1 = fully supported, 0 = not supported at all."
    )
    return await _llm_score(llm, prompt)


async def _score_answer_relevancy(llm: ChatOpenAI, question: str, answer: str) -> float:
    prompt = (
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        "Rate how relevant and complete the answer is to the question. "
        "1 = perfectly relevant and complete, 0 = completely irrelevant."
    )
    return await _llm_score(llm, prompt)


async def _score_context_precision(llm: ChatOpenAI, question: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Question: {question}\n"
        f"Retrieved contexts:\n{ctx}\n\n"
        "Rate how relevant the retrieved contexts are to the question. "
        "1 = all context is highly relevant, 0 = context is completely irrelevant."
    )
    return await _llm_score(llm, prompt)


async def _score_context_recall(llm: ChatOpenAI, expected: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Reference answer: {expected}\n"
        f"Retrieved contexts:\n{ctx}\n\n"
        "Rate how much of the information needed to produce the reference answer is present in the retrieved contexts. "
        "1 = all needed information is present, 0 = none of the needed information is present."
    )
    return await _llm_score(llm, prompt)


async def generate_qa_pairs(doc_content: str, n: int, llm: ChatOpenAI) -> list[dict]:
    prompt = (
        f"Generate exactly {n} diverse question-answer pairs based on the document below. "
        "Questions should cover different sections and topics. "
        "Return ONLY a JSON array with this format: "
        '[{"question": "...", "answer": "..."}, ...]\n\n'
        f"Document:\n{doc_content[:7000]}"
    )
    response = await llm.ainvoke(prompt)
    text = response.content.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    raw = match.group() if match else text
    pairs = json.loads(raw)
    return pairs[:n]


async def evaluate_document(
    file_path: str,
    persist_directory: str,
    num_questions: int,
    progress_cb=None,
) -> list[dict]:
    llm = _get_llm()
    embeddings = _get_embedding_model()

    docs = _load_pdf(file_path)
    doc_content = "\n".join(d.page_content for d in docs)

    if progress_cb:
        await progress_cb("Generating test questions...", 10)

    qa_pairs = await generate_qa_pairs(doc_content, num_questions, llm)

    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5, "filter": {"source": file_path}})

    results = []
    for i, qa in enumerate(qa_pairs):
        question = qa.get("question", "")
        expected = qa.get("answer", "")

        if progress_cb:
            pct = 15 + int((i / len(qa_pairs)) * 70)
            await progress_cb(f"Evaluating question {i + 1}/{len(qa_pairs)}...", pct)

        context_docs = await asyncio.to_thread(retriever.invoke, question)
        contexts = [d.page_content for d in context_docs]

        context_str = "\n\n".join(contexts)
        rag_prompt = f"Use the following context to answer the question.\n\nContext:\n{context_str}\n\nQuestion: {question}"
        rag_response = await llm.ainvoke(rag_prompt)
        rag_answer = rag_response.content

        fa, ar, cp, cr = await asyncio.gather(
            _score_faithfulness(llm, question, rag_answer, contexts),
            _score_answer_relevancy(llm, question, rag_answer),
            _score_context_precision(llm, question, contexts),
            _score_context_recall(llm, expected, contexts),
        )

        results.append({
            "question": question,
            "expected_answer": expected,
            "rag_answer": rag_answer,
            "faithfulness": round(fa, 3),
            "answer_relevancy": round(ar, 3),
            "context_precision": round(cp, 3),
            "context_recall": round(cr, 3),
        })

    return results

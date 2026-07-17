import asyncio
import json
import os
import re

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.language_models import BaseChatModel
from langchain_openrouter import ChatOpenRouter

load_dotenv()

from .rag_vector_db import get_embedding_model, _load_document, ensure_recursive_chunks
from tools import hybrid_retrieve


def _get_llm(model_id: str) -> BaseChatModel:
    """Retries transient failures (dropped connections, DNS blips) up to 3x with
    backoff -- evaluate_document fires up to 8 concurrent LLM calls per question,
    so a single flaky connection previously aborted the entire evaluation run."""
    return ChatOpenRouter(model=model_id).with_retry(stop_after_attempt=3, wait_exponential_jitter=True)


async def _llm_score(llm: BaseChatModel, prompt: str) -> float:
    response = await llm.ainvoke(prompt + "\n\nRespond with only a decimal number between 0 and 1, nothing else.")
    text = response.content.strip()
    match = re.search(r"1(?:\.0+)?|0(?:\.\d+)?|\.\d+", text)
    return min(1.0, max(0.0, float(match.group()))) if match else 0.0


async def _score_faithfulness(llm: BaseChatModel, question: str, answer: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Context:\n{ctx}\n\n"
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        "Rate how faithfully the answer is supported by the context alone (ignore prior knowledge). "
        "1 = fully supported, 0 = not supported at all."
    )
    return await _llm_score(llm, prompt)


async def _score_answer_relevancy(llm: BaseChatModel, question: str, answer: str) -> float:
    prompt = (
        f"Question: {question}\n"
        f"Answer: {answer}\n\n"
        "Rate how relevant and complete the answer is to the question. "
        "1 = perfectly relevant and complete, 0 = completely irrelevant."
    )
    return await _llm_score(llm, prompt)


async def _score_context_precision(llm: BaseChatModel, question: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Question: {question}\n"
        f"Retrieved contexts:\n{ctx}\n\n"
        "Rate how relevant the retrieved contexts are to the question. "
        "1 = all context is highly relevant, 0 = context is completely irrelevant."
    )
    return await _llm_score(llm, prompt)


async def _score_context_recall(llm: BaseChatModel, expected: str, contexts: list[str]) -> float:
    ctx = "\n---\n".join(contexts)
    prompt = (
        f"Reference answer: {expected}\n"
        f"Retrieved contexts:\n{ctx}\n\n"
        "Rate how much of the information needed to produce the reference answer is present in the retrieved contexts. "
        "1 = all needed information is present, 0 = none of the needed information is present."
    )
    return await _llm_score(llm, prompt)


async def generate_qa_pairs(doc_content: str, n: int, llm: BaseChatModel) -> list[dict]:
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


async def _run_strategy(retrieve_fn, question: str, expected: str, answer_llm: BaseChatModel, judge_llm: BaseChatModel) -> dict:
    """Retrieve contexts for one (chunking, search) strategy, RAG-answer, and score the
    4 metrics. `retrieve_fn` is a zero-extra-arg sync callable taking only `question`."""
    context_docs = await asyncio.to_thread(retrieve_fn, question)
    contexts = [d.page_content for d in context_docs]

    context_str = "\n\n".join(contexts)
    rag_prompt = f"Use the following context to answer the question.\n\nContext:\n{context_str}\n\nQuestion: {question}"
    rag_response = await answer_llm.ainvoke(rag_prompt)
    rag_answer = rag_response.content

    fa, ar, cp, cr = await asyncio.gather(
        _score_faithfulness(judge_llm, question, rag_answer, contexts),
        _score_answer_relevancy(judge_llm, question, rag_answer),
        _score_context_precision(judge_llm, question, contexts),
        _score_context_recall(judge_llm, expected, contexts),
    )

    return {
        "rag_answer": rag_answer,
        "faithfulness": round(fa, 3),
        "answer_relevancy": round(ar, 3),
        "context_precision": round(cp, 3),
        "context_recall": round(cr, 3),
    }


async def evaluate_document(
    file_path: str,
    persist_directory: str,
    num_questions: int,
    answer_model_id: str,
    judge_model_id: str,
    progress_cb=None,
    embedding_model_id: str | None = None,
    strategies: list[str] = ("semantic", "semantic_hybrid"),
    session_id: str | None = None,
) -> list[dict]:
    answer_llm = _get_llm(answer_model_id)
    judge_llm = _get_llm(judge_model_id)
    embeddings = get_embedding_model(embedding_model_id)

    docs = _load_document(file_path)
    doc_content = "\n".join(d.page_content for d in docs)

    if progress_cb:
        await progress_cb("Generating test questions...", 10)

    qa_pairs = await generate_qa_pairs(doc_content, num_questions, judge_llm)

    # Build a retrieval closure per requested strategy, opening each backing ChromaDB
    # (and, for the recursive strategies, lazily chunking+ingesting it) only if needed.
    retrievers = {}
    if "semantic" in strategies or "semantic_hybrid" in strategies:
        semantic_vs = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        semantic_filter = {"source": file_path}
        semantic_retriever = semantic_vs.as_retriever(search_kwargs={"k": 5, "filter": semantic_filter})
        if "semantic" in strategies:
            retrievers["semantic"] = lambda q: semantic_retriever.invoke(q)
        if "semantic_hybrid" in strategies:
            retrievers["semantic_hybrid"] = lambda q: hybrid_retrieve(semantic_vs, q, judge_llm, 5, 10, semantic_filter)

    if "recursive" in strategies or "recursive_hybrid" in strategies:
        recursive_dir = ensure_recursive_chunks(file_path, session_id, embedding_model_id)
        recursive_vs = Chroma(persist_directory=recursive_dir, embedding_function=embeddings)
        recursive_filter = {"source": file_path}
        recursive_retriever = recursive_vs.as_retriever(search_kwargs={"k": 5, "filter": recursive_filter})
        if "recursive" in strategies:
            retrievers["recursive"] = lambda q: recursive_retriever.invoke(q)
        if "recursive_hybrid" in strategies:
            retrievers["recursive_hybrid"] = lambda q: hybrid_retrieve(recursive_vs, q, judge_llm, 5, 10, recursive_filter)

    results = []
    for i, qa in enumerate(qa_pairs):
        question = qa.get("question", "")
        expected = qa.get("answer", "")

        if progress_cb:
            pct = 15 + int((i / len(qa_pairs)) * 70)
            await progress_cb(f"Evaluating question {i + 1}/{len(qa_pairs)}...", pct)

        strategy_names = list(retrievers.keys())
        strategy_results = await asyncio.gather(*(
            _run_strategy(retrievers[name], question, expected, answer_llm, judge_llm)
            for name in strategy_names
        ))

        results.append({
            "question": question,
            "expected_answer": expected,
            "results": dict(zip(strategy_names, strategy_results)),
        })

    return results

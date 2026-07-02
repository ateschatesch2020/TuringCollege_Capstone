import threading
import pymupdf4llm
import shutil
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PERSIST_DIR = os.path.join(_ROOT, "chroma_db")
_SESSIONS_DIR = os.path.join(_PERSIST_DIR, "sessions")

def _get_embedding_model():
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"))


def _load_pdf(file_path: str) -> list[Document]:
    """Convert PDF to Markdown via pymupdf4llm, preserving list and heading structure."""
    md_text = pymupdf4llm.to_markdown(file_path)
    return [Document(page_content=md_text, metadata={"source": file_path})]


def delete_document(file_path: str, persist_directory: str) -> int:
    """Delete all ChromaDB chunks whose source metadata matches file_path. Returns deleted count."""
    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=_get_embedding_model())
    results = vectorstore.get(where={"source": file_path})
    ids = results["ids"]
    if ids:
        vectorstore.delete(ids)
    return len(ids)


def get_session_persist_dir(session_id: str) -> str:
    return os.path.join(_SESSIONS_DIR, session_id)


def add_document_for_session(file_path: str, session_id: str,
                             cancel_event: threading.Event = None) -> int:
    """Embed a PDF into a session-specific ChromaDB. Returns chunk count."""
    session_dir = get_session_persist_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)

    docs = _load_pdf(file_path)
    chunks = SemanticChunker(_get_embedding_model()).split_documents(docs)

    if cancel_event is not None and cancel_event.is_set():
        return 0

    vectorstore = Chroma(persist_directory=session_dir, embedding_function=_get_embedding_model())
    vectorstore.add_documents(chunks)
    return len(chunks)


def delete_session_vectorstore(session_id: str) -> None:
    """Remove the entire ChromaDB directory for a session."""
    session_dir = get_session_persist_dir(session_id)
    shutil.rmtree(session_dir, ignore_errors=True)

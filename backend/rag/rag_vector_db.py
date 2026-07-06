import threading
import pymupdf4llm
from langchain_core.documents import Document
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PERSIST_DIR = os.path.join(_ROOT, "chroma_db")
_SHARED_DIR = os.path.join(_PERSIST_DIR, "shared")

def _get_embedding_model():
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"))


def _load_pdf(file_path: str) -> list[Document]:
    """Convert PDF to Markdown via pymupdf4llm, preserving list and heading structure."""
    md_text = pymupdf4llm.to_markdown(file_path)
    return [Document(page_content=md_text, metadata={"source": file_path})]


def delete_document(file_path: str, session_id: str, persist_directory: str) -> int:
    """Delete all ChromaDB chunks whose session_id and source metadata match. Returns deleted count."""
    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=_get_embedding_model())
    results = vectorstore.get(where={"$and": [{"session_id": session_id}, {"source": file_path}]})
    ids = results["ids"]
    if ids:
        vectorstore.delete(ids)
    return len(ids)


def get_shared_persist_dir() -> str:
    return _SHARED_DIR


def add_document_for_session(file_path: str, session_id: str, user_id: str = None,
                             cancel_event: threading.Event = None) -> int:
    """Embed a PDF into the shared ChromaDB, tagged with session_id/document_name/user_id metadata. Returns chunk count."""
    os.makedirs(_SHARED_DIR, exist_ok=True)

    docs = _load_pdf(file_path)
    docs[0].metadata["session_id"] = session_id
    docs[0].metadata["document_name"] = os.path.basename(file_path)
    if user_id:
        docs[0].metadata["user_id"] = user_id
    chunks = SemanticChunker(_get_embedding_model()).split_documents(docs)

    if cancel_event is not None and cancel_event.is_set():
        return 0

    delete_document(file_path, session_id, _SHARED_DIR)  # replace any prior ingestion of this same file instead of accumulating duplicates
    vectorstore = Chroma(persist_directory=_SHARED_DIR, embedding_function=_get_embedding_model())
    vectorstore.add_documents(chunks)
    return len(chunks)


def delete_session_vectorstore(session_id: str) -> None:
    """Remove all chunks belonging to a session from the shared ChromaDB."""
    vectorstore = Chroma(persist_directory=_SHARED_DIR, embedding_function=_get_embedding_model())
    results = vectorstore.get(where={"session_id": session_id})
    ids = results["ids"]
    if ids:
        vectorstore.delete(ids)

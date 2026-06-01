from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
import os
load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PERSIST_DIR = os.path.join(_ROOT, "chroma_db")


def _get_embedding_model():
    return OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"))


def add_document(file_path: str, persist_directory: str = _PERSIST_DIR) -> int:
    """Load PDF, chunk (300/20), embed, and add chunks to existing ChromaDB. Returns chunk count."""
    delete_document(file_path, persist_directory)  # remove stale chunks on re-upload

    loader = PyPDFLoader(file_path)
    docs = loader.load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=20).split_documents(docs)

    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=_get_embedding_model())
    vectorstore.add_documents(chunks)
    return len(chunks)


def delete_document(file_path: str, persist_directory: str = _PERSIST_DIR) -> int:
    """Delete all ChromaDB chunks whose source metadata matches file_path. Returns deleted count."""
    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=_get_embedding_model())
    results = vectorstore.get(where={"source": file_path})
    ids = results["ids"]
    if ids:
        vectorstore.delete(ids)
    return len(ids)


if __name__ == "__main__":
    file_name = os.path.join(_ROOT, "documents", "Corporate_Travel_and_Expense_Policy.pdf")
    loader = PyPDFLoader(file_name)
    docs = loader.load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=20).split_documents(docs)

    print("creating vector database...")
    Chroma.from_documents(
        documents=chunks,
        embedding=_get_embedding_model(),
        persist_directory=_PERSIST_DIR
    )
    print(f"Successfull! Data is stored to {_PERSIST_DIR}.")

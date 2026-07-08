import asyncio
import functools
import inspect
import logging
import os
import shutil
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCUMENTS_DIR = os.path.join(_ROOT, "documents")
_SESSION_DOCS_DIR = os.path.join(_DOCUMENTS_DIR, "sessions")
_GENERATED_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_files")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_ROOT, "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from chatbot import ChatbotManager
from chatform import FormManager
from models_catalog import MODEL_CATALOG, EMBEDDING_MODEL_CATALOG, get_embedding_model_info, DEFAULT_MODEL_ID
from tools import list_session_documents
from rag.rag_vector_db import (delete_document,
                               add_document_for_session, delete_session_vectorstore,
                               get_persist_dir_for_embedding, SUPPORTED_EXTENSIONS)
from sse_utils import sse_event, poll_for_cancel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pathlib import Path

_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://127.0.0.1:5500,http://localhost:5173,http://localhost:8081"
).split(",")

app = FastAPI(title="Chatbot Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

chatbot = ChatbotManager()
form_manager = FormManager()


def handle_errors(message: str, id_param: str = None):
    """Decorator for sync route handlers: runs the handler, and on any exception logs
    `message` (with the named parameter's value substituted in for %s, if id_param is
    given) and raises HTTPException(500, detail=str(e)) -- replacing the identical
    try/except/log/raise block that was previously repeated in 7 route handlers."""
    def decorator(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except HTTPException:
                raise  # an intentional HTTP error response (e.g. a 400/404 validation check) -- don't rewrap as a 500
            except Exception as e:
                if id_param:
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()
                    logger.error(message, bound.arguments[id_param], exc_info=True)
                else:
                    logger.error(message, exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        return wrapper
    return decorator


def resolve_session_embedding(session_id: str):
    """Looks up a session's embedding_model_id and its persist directory together,
    since every caller that needs one needs the other. Returns
    (embedding_model_id, persist_dir)."""
    embedding_model_id = chatbot.get_session_embedding_model(session_id)
    persist_dir = get_persist_dir_for_embedding(embedding_model_id)
    return embedding_model_id, persist_dir

class CreateSessionRequest(BaseModel):
    user_id: str
    title: str = "New Chat Session"
    session_id: Optional[str] = None
    model: Optional[str] = None
    embedding_model: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    query: str
    model: Optional[str] = None

class MessageResponse(BaseModel):
    content: str
    role: str = "assistant"

class RenameSessionRequest(BaseModel):
    title: str

class SetSessionModelRequest(BaseModel):
    model: str

class EvaluateRequest(BaseModel):
    filename: str
    num_questions: int = 20
    session_id: str
    answer_model_id: str = DEFAULT_MODEL_ID
    judge_model_id: str = DEFAULT_MODEL_ID

class IngestPathsRequest(BaseModel):
    paths: List[str]
    session_id: str
    embedding_model_id: Optional[str] = None

class FormSearchRequest(BaseModel):
    keyword: str
    exact_match: bool = False
    contains_name: bool = True

@app.post("/sessions/create")
@handle_errors("create_session failed")
def create_session(request: CreateSessionRequest):
    if request.embedding_model and not get_embedding_model_info(request.embedding_model):
        raise HTTPException(status_code=400, detail=f"Unknown embedding_model: {request.embedding_model}")
    session_id = chatbot.create_session(
        user_id=request.user_id, title=request.title, session_id=request.session_id,
        model=request.model, embedding_model=request.embedding_model
    )
    return {"session_id": session_id}


@app.get("/models")
def list_models():
    return {"models": MODEL_CATALOG}

@app.get("/embedding-models")
def list_embedding_models():
    return {"embedding_models": EMBEDDING_MODEL_CATALOG}

@app.delete("/sessions/{session_id}")
@handle_errors("delete_session failed for %s", id_param="session_id")
def delete_session(session_id: str):
    embedding_model_id, persist_dir = resolve_session_embedding(session_id)  # look up before deleting the row
    chatbot.delete_session(session_id=session_id)
    delete_session_vectorstore(session_id, persist_dir, embedding_model_id)
    shutil.rmtree(os.path.join(_SESSION_DOCS_DIR, session_id), ignore_errors=True)
    return {"session_id": session_id}

@app.get("/sessions/{user_id}")
@handle_errors("list_sessions failed for user %s", id_param="user_id")
def list_sessions(user_id: str):
    sessions = chatbot.list_sessions(user_id=user_id)
    return {"sessions": sessions}

@app.get("/sessions/{session_id}/info")
def get_session_info(session_id: str):
    info = chatbot.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info

@app.patch("/sessions/{session_id}/rename")
@handle_errors("rename_session failed for %s", id_param="session_id")
def rename_session(session_id: str, request: RenameSessionRequest):
    chatbot.update_session_title(session_id=session_id, new_title=request.title)
    return {"session_id": session_id, "title": request.title}

@app.patch("/sessions/{session_id}/model")
@handle_errors("set_session_model failed for %s", id_param="session_id")
def set_session_model(session_id: str, request: SetSessionModelRequest):
    chatbot.update_session_model(session_id=session_id, model=request.model)
    return {"session_id": session_id, "model": request.model}

@app.get("/history/{session_id}")
@handle_errors("get_history failed for %s", id_param="session_id")
def get_history(session_id: str):
    messages = chatbot.get_messages(session_id=session_id)
    result = []
    for msg in messages:
        role = "user" if msg.type == "human" else "assistant"
        result.append(MessageResponse(content=msg.content, role=role))
    return {"messages": result}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    def iterate_responses():
        try:
            for response in chatbot.chat_stream(session_id=request.session_id, query=request.query, model_id=request.model):
                yield response
        except Exception as e:
            logger.error("Unhandled error in chat stream for session %s: %s", request.session_id, str(e), exc_info=True)
            yield f"Sorry, I encountered an error while processing your request: {e}"

    return StreamingResponse(iterate_responses(), media_type="text/plain")
    

@app.get("/sessions/{session_id}/token-usage")
def get_token_usage(session_id: str):
    return chatbot.get_token_usage(session_id)


@app.get("/documents")
def list_documents(session_id: str):
    files = list_session_documents(_SESSION_DOCS_DIR, session_id)
    return {"documents": files, "count": len(files)}


@app.post("/documents/upload")
async def upload_document(request: Request, file: UploadFile = File(...), session_id: str = Form(...)):
    if os.path.splitext(file.filename)[1].lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    session_docs_dir = os.path.join(_SESSION_DOCS_DIR, session_id)
    os.makedirs(session_docs_dir, exist_ok=True)
    file_path = os.path.join(session_docs_dir, file.filename)
    content = await file.read()
    user_id = chatbot.get_user_id_for_session(session_id)
    embedding_model_id = chatbot.get_session_embedding_model(session_id)

    async def event_stream():
        cancel_event = threading.Event()
        try:
            yield sse_event({"stage": "Saving document...", "progress": 10})
            with open(file_path, "wb") as f:
                f.write(content)

            yield sse_event({"stage": "Generating embeddings...", "progress": 30})

            add_task = asyncio.create_task(
                asyncio.to_thread(add_document_for_session, file_path, session_id, user_id=user_id,
                                  cancel_event=cancel_event, embedding_model_id=embedding_model_id)
            )

            if await poll_for_cancel(request, add_task, cancel_event):
                if os.path.exists(file_path):
                    os.remove(file_path)
                logger.info("Upload cancelled by client: %s", file.filename)
                return

            chunk_count = add_task.result()

            if cancel_event.is_set() or chunk_count == 0:
                return

            yield sse_event({"stage": "Complete", "progress": 100, "chunks": chunk_count, "filename": file.filename})
            logger.info("Uploaded and indexed %s (%d chunks)", file.filename, chunk_count)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error("upload_document failed for %s", file.filename, exc_info=True)
            yield sse_event({"stage": "Error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/documents/ingest-paths")
async def ingest_paths_endpoint(request: Request, body: IngestPathsRequest):
    projects_dir = os.getenv("PROJECTS_DIR", "")
    if not projects_dir:
        raise HTTPException(status_code=400, detail="PROJECTS_DIR is not configured on the server.")

    abs_projects = os.path.normcase(os.path.abspath(projects_dir))
    abs_projects_prefix = abs_projects if abs_projects.endswith(os.sep) else abs_projects + os.sep

    valid_paths = []
    errors = []
    for p in body.paths:
        abs_p = os.path.normcase(os.path.abspath(p))
        if not (abs_p == abs_projects or abs_p.startswith(abs_projects_prefix)):
            errors.append(f"Access denied: {p}")
            continue
        if os.path.splitext(p)[1].lower() not in SUPPORTED_EXTENSIONS:
            errors.append(f"Unsupported file type: {p}")
            continue
        if not os.path.isfile(abs_p):
            errors.append(f"File not found: {p}")
            continue
        valid_paths.append(abs_p)

    if not valid_paths:
        raise HTTPException(status_code=400, detail=f"No valid paths. {'; '.join(errors)}")

    session_id = body.session_id
    user_id = chatbot.get_user_id_for_session(session_id)
    embedding_model_id = chatbot.get_session_embedding_model(session_id) or body.embedding_model_id

    async def event_stream():
        total = len(valid_paths)
        for idx, src_path in enumerate(valid_paths):
            fname = os.path.basename(src_path)
            cancel_event = threading.Event()
            try:
                session_docs_dir = os.path.join(_SESSION_DOCS_DIR, session_id)
                os.makedirs(session_docs_dir, exist_ok=True)
                dest_path = os.path.join(session_docs_dir, fname)
                yield sse_event({"stage": "Saving document...", "progress": 10, "filename": fname, "file_index": idx, "total_files": total})
                shutil.copy2(src_path, dest_path)
                yield sse_event({"stage": "Generating embeddings...", "progress": 30, "filename": fname, "file_index": idx, "total_files": total})
                add_task = asyncio.create_task(
                    asyncio.to_thread(add_document_for_session, dest_path, session_id, user_id=user_id,
                                      cancel_event=cancel_event, embedding_model_id=embedding_model_id)
                )

                if await poll_for_cancel(request, add_task, cancel_event):
                    logger.info("ingest-paths cancelled by client: %s", fname)
                    return

                chunk_count = add_task.result()
                if cancel_event.is_set() or chunk_count == 0:
                    return

                yield sse_event({"stage": "Complete", "progress": 100, "chunks": chunk_count, "filename": fname, "file_index": idx, "total_files": total})
                logger.info("Ingested from path %s (%d chunks)", fname, chunk_count)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("ingest_paths failed for %s", src_path, exc_info=True)
                yield sse_event({"stage": "Error", "error": str(e), "filename": fname, "file_index": idx, "total_files": total})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/form/search")
async def form_search(req: FormSearchRequest):
    async def event_stream():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def worker():
            try:
                for kind, payload in form_manager.search_with_progress(
                    req.keyword, req.exact_match, req.contains_name
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))

        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                kind, payload = await queue.get()
                if kind == "counting":
                    yield sse_event({"stage": "Counting files...", "progress": None})
                elif kind == "progress":
                    yield sse_event({"stage": "Searching...", "progress": payload})
                elif kind == "done":
                    yield sse_event({"stage": "Complete", "progress": 100, "result": payload})
                    break
                elif kind == "error":
                    logger.error("form_search failed for keyword '%s': %s", req.keyword, payload)
                    yield sse_event({"stage": "Error", "error": payload})
                    break
        finally:
            await task

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/files/{filename}")
def download_generated_file(filename: str):
    safe_path = Path(_GENERATED_FILES_DIR) / Path(filename).name
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(safe_path), filename=Path(filename).name)


@app.delete("/documents/{filename}")
@handle_errors("delete_document failed for %s", id_param="filename")
def delete_document_endpoint(filename: str, session_id: str):
    file_path = os.path.join(_SESSION_DOCS_DIR, session_id, filename)
    embedding_model_id, persist_dir = resolve_session_embedding(session_id)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    removed = delete_document(file_path, session_id, persist_dir, embedding_model_id)
    os.remove(file_path)
    logger.info("Deleted %s (%d chunks removed from ChromaDB)", filename, removed)
    return {"filename": filename, "chunks_removed": removed}


@app.post("/evaluate")
async def evaluate_endpoint(request: EvaluateRequest):
    from rag.ragas_evaluator import evaluate_document
    file_path = os.path.join(_SESSION_DOCS_DIR, request.session_id, request.filename)
    embedding_model_id, persist_dir = resolve_session_embedding(request.session_id)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Document not found")

    async def event_stream():
        try:
            # Generator-based progress doesn't work inside a callback; collect via queue
            queue: asyncio.Queue = asyncio.Queue()

            async def cb(stage: str, pct: int):
                await queue.put({"stage": stage, "progress": pct})

            async def run_eval():
                try:
                    results = await evaluate_document(
                        file_path=file_path,
                        persist_directory=persist_dir,
                        num_questions=request.num_questions,
                        answer_model_id=request.answer_model_id,
                        judge_model_id=request.judge_model_id,
                        progress_cb=cb,
                        embedding_model_id=embedding_model_id,
                    )
                    await queue.put({"done": True, "results": results})
                except Exception as e:
                    logger.error("evaluate_document failed for %s", request.filename, exc_info=True)
                    await queue.put({"done": True, "error": str(e)})

            task = asyncio.create_task(run_eval())

            while True:
                msg = await queue.get()
                if msg.get("done"):
                    if "error" in msg:
                        yield sse_event({"stage": "Error", "error": msg["error"]})
                    else:
                        yield sse_event({"stage": "Complete", "progress": 100, "results": msg["results"]})
                    break
                yield sse_event({"stage": msg["stage"], "progress": msg["progress"]})

            await task
        except Exception as e:
            logger.error("evaluate_endpoint failed for %s", request.filename, exc_info=True)
            yield sse_event({"stage": "Error", "error": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("API_HOST", "localhost"), port=int(os.getenv("API_PORT", "8001")))
    


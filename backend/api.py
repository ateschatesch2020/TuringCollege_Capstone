import asyncio
import json
import logging
import os
import shutil
import threading

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCUMENTS_DIR = os.path.join(_ROOT, "documents")
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

from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from chatbot import ChatbotManager
from rag.rag_vector_db import add_document, delete_document, _PERSIST_DIR
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pathlib import Path

app = FastAPI(title="Chatbot Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5173", "http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

chatbot = ChatbotManager()

class CreateSessionRequest(BaseModel):
    user_id: str
    title: str = "New Chat Session"

class ChatRequest(BaseModel):
    session_id: str
    query: str  

class MessageResponse(BaseModel):
    content: str
    role: str = "assistant"

class RenameSessionRequest(BaseModel):
    title: str

class EvaluateRequest(BaseModel):
    filename: str
    num_questions: int = 20

class IngestPathsRequest(BaseModel):
    paths: List[str]

@app.post("/sessions/create")
def create_session(request: CreateSessionRequest):
    try:
        session_id = chatbot.create_session(user_id=request.user_id, title=request.title)
        return {"session_id": session_id}
    except Exception as e:
        logger.error("create_session failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        session_id = chatbot.delete_session(session_id=session_id)
        return {"session_id": session_id}
    except Exception as e:
        logger.error("delete_session failed for %s", session_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{user_id}")
def list_sessions(user_id: str):
    try:
        sessions = chatbot.list_sessions(user_id=user_id)
        return {"sessions": sessions}
    except Exception as e:
        logger.error("list_sessions failed for user %s", user_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sessions/{session_id}/rename")
def rename_session(session_id: str, request: RenameSessionRequest):
    try:
        chatbot.update_session_title(session_id=session_id, new_title=request.title)
        return {"session_id": session_id, "title": request.title}
    except Exception as e:
        logger.error("rename_session failed for %s", session_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{session_id}")
def get_history(session_id: str):
    try:
        messages = chatbot.get_messages(session_id=session_id)
        result = []
        for msg in messages:
            role = "user" if msg.type == "human" else "assistant"
            result.append(MessageResponse(content=msg.content, role=role))
        return {"messages": result}
    except Exception as e:
        logger.error("get_history failed for %s", session_id, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    def iterate_responses():
        try:
            for response in chatbot.chat_stream(session_id=request.session_id, query=request.query):
                yield response
        except Exception:
            logger.error("Unhandled error in chat stream for session %s", request.session_id, exc_info=True)
            yield "Sorry, I encountered an error while processing your request."

    return StreamingResponse(iterate_responses(), media_type="text/plain")
    

@app.get("/sessions/{session_id}/token-usage")
def get_token_usage(session_id: str):
    return chatbot.get_token_usage(session_id)


@app.get("/documents")
def list_documents():
    files = sorted(f for f in os.listdir(_DOCUMENTS_DIR) if f.lower().endswith(".pdf"))
    return {"documents": files}


@app.post("/documents/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    file_path = os.path.join(_DOCUMENTS_DIR, file.filename)
    content = await file.read()

    async def event_stream():
        cancel_event = threading.Event()
        try:
            yield f"data: {json.dumps({'stage': 'Saving document...', 'progress': 10})}\n\n"
            with open(file_path, "wb") as f:
                f.write(content)

            yield f"data: {json.dumps({'stage': 'Generating embeddings...', 'progress': 30})}\n\n"

            add_task = asyncio.create_task(
                asyncio.to_thread(add_document, file_path, cancel_event=cancel_event)
            )

            while not add_task.done():
                await asyncio.sleep(0.5)
                if await request.is_disconnected():
                    cancel_event.set()
                    add_task.cancel()
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    logger.info("Upload cancelled by client: %s", file.filename)
                    return

            chunk_count = add_task.result()

            if cancel_event.is_set() or chunk_count == 0:
                return

            yield f"data: {json.dumps({'stage': 'Refreshing index...', 'progress': 85})}\n\n"
            await asyncio.to_thread(chatbot.reload_vectorstore)
            yield f"data: {json.dumps({'stage': 'Complete', 'progress': 100, 'chunks': chunk_count, 'filename': file.filename})}\n\n"
            logger.info("Uploaded and indexed %s (%d chunks)", file.filename, chunk_count)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error("upload_document failed for %s", file.filename, exc_info=True)
            yield f"data: {json.dumps({'stage': 'Error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/documents/ingest-paths")
async def ingest_paths_endpoint(request: Request, body: IngestPathsRequest):
    projects_dir = os.getenv("PROJECTS_DIR", "")
    if not projects_dir:
        raise HTTPException(status_code=400, detail="PROJECTS_DIR is not configured on the server.")

    abs_projects = os.path.abspath(projects_dir)

    valid_paths = []
    errors = []
    for p in body.paths:
        abs_p = os.path.abspath(p)
        if not (abs_p == abs_projects or abs_p.startswith(abs_projects + os.sep)):
            errors.append(f"Access denied: {p}")
            continue
        if not p.lower().endswith(".pdf"):
            errors.append(f"Not a PDF: {p}")
            continue
        if not os.path.isfile(abs_p):
            errors.append(f"File not found: {p}")
            continue
        valid_paths.append(abs_p)

    if not valid_paths:
        raise HTTPException(status_code=400, detail=f"No valid PDF paths. {'; '.join(errors)}")

    async def event_stream():
        total = len(valid_paths)
        for idx, src_path in enumerate(valid_paths):
            fname = os.path.basename(src_path)
            dest_path = os.path.join(_DOCUMENTS_DIR, fname)
            cancel_event = threading.Event()
            try:
                yield f"data: {json.dumps({'stage': 'Saving document...', 'progress': 10, 'filename': fname, 'file_index': idx, 'total_files': total})}\n\n"
                shutil.copy2(src_path, dest_path)

                yield f"data: {json.dumps({'stage': 'Generating embeddings...', 'progress': 30, 'filename': fname, 'file_index': idx, 'total_files': total})}\n\n"
                add_task = asyncio.create_task(
                    asyncio.to_thread(add_document, dest_path, cancel_event=cancel_event)
                )
                while not add_task.done():
                    await asyncio.sleep(0.5)
                    if await request.is_disconnected():
                        cancel_event.set()
                        add_task.cancel()
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        logger.info("ingest-paths cancelled by client: %s", fname)
                        return

                chunk_count = add_task.result()
                if cancel_event.is_set() or chunk_count == 0:
                    return

                yield f"data: {json.dumps({'stage': 'Refreshing index...', 'progress': 85, 'filename': fname, 'file_index': idx, 'total_files': total})}\n\n"
                await asyncio.to_thread(chatbot.reload_vectorstore)
                yield f"data: {json.dumps({'stage': 'Complete', 'progress': 100, 'chunks': chunk_count, 'filename': fname, 'file_index': idx, 'total_files': total})}\n\n"
                logger.info("Ingested from path %s (%d chunks)", fname, chunk_count)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("ingest_paths failed for %s", src_path, exc_info=True)
                yield f"data: {json.dumps({'stage': 'Error', 'error': str(e), 'filename': fname, 'file_index': idx, 'total_files': total})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/files/{filename}")
def download_generated_file(filename: str):
    safe_path = Path(_GENERATED_FILES_DIR) / Path(filename).name
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(safe_path), filename=Path(filename).name)


@app.delete("/documents/{filename}")
def delete_document_endpoint(filename: str):
    file_path = os.path.join(_DOCUMENTS_DIR, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        removed = delete_document(file_path)
        os.remove(file_path)
        chatbot.reload_vectorstore()
        logger.info("Deleted %s (%d chunks removed from ChromaDB)", filename, removed)
        return {"filename": filename, "chunks_removed": removed}
    except Exception as e:
        logger.error("delete_document failed for %s", filename, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate")
async def evaluate_endpoint(request: EvaluateRequest):
    from rag.ragas_evaluator import evaluate_document
    file_path = os.path.join(_DOCUMENTS_DIR, request.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Document not found")

    async def event_stream():
        try:
            async def progress_cb(stage: str, pct: int):
                yield f"data: {json.dumps({'stage': stage, 'progress': pct})}\n\n"

            # Generator-based progress doesn't work inside a callback; collect via queue
            import asyncio
            queue: asyncio.Queue = asyncio.Queue()

            async def cb(stage: str, pct: int):
                await queue.put({"stage": stage, "progress": pct})

            async def run_eval():
                results = await evaluate_document(
                    file_path=file_path,
                    persist_directory=_PERSIST_DIR,
                    num_questions=request.num_questions,
                    progress_cb=cb,
                )
                await queue.put({"done": True, "results": results})

            task = asyncio.create_task(run_eval())

            while True:
                msg = await queue.get()
                if msg.get("done"):
                    yield f"data: {json.dumps({'stage': 'Complete', 'progress': 100, 'results': msg['results']})}\n\n"
                    break
                yield f"data: {json.dumps({'stage': msg['stage'], 'progress': msg['progress']})}\n\n"

            await task
        except Exception as e:
            logger.error("evaluate_endpoint failed for %s", request.filename, exc_info=True)
            yield f"data: {json.dumps({'stage': 'Error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001)
    


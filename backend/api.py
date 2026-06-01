import asyncio
import json
import logging
import os
import shutil

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCUMENTS_DIR = os.path.join(_ROOT, "documents")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(_ROOT, "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File
from chatbot import ChatbotManager
from rag.rag_vector_db import add_document, delete_document
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="Chatbot Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5173"],
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
    

@app.get("/documents")
def list_documents():
    files = sorted(f for f in os.listdir(_DOCUMENTS_DIR) if f.lower().endswith(".pdf"))
    return {"documents": files}


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    file_path = os.path.join(_DOCUMENTS_DIR, file.filename)
    content = await file.read()

    async def event_stream():
        try:
            yield f"data: {json.dumps({'stage': 'Saving document...', 'progress': 10})}\n\n"
            with open(file_path, "wb") as f:
                f.write(content)
            yield f"data: {json.dumps({'stage': 'Generating embeddings...', 'progress': 30})}\n\n"
            chunk_count = await asyncio.to_thread(add_document, file_path)
            yield f"data: {json.dumps({'stage': 'Refreshing index...', 'progress': 85})}\n\n"
            await asyncio.to_thread(chatbot.reload_vectorstore)
            yield f"data: {json.dumps({'stage': 'Complete', 'progress': 100, 'chunks': chunk_count, 'filename': file.filename})}\n\n"
            logger.info("Uploaded and indexed %s (%d chunks)", file.filename, chunk_count)
        except Exception as e:
            logger.error("upload_document failed for %s", file.filename, exc_info=True)
            yield f"data: {json.dumps({'stage': 'Error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001)
    


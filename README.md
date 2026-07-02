# Office Helper Assistant

A per-session document assistant: each chat session works with the PDFs uploaded into it —
answering questions, extracting information, and generating summaries, presentations, Word
documents, and PDFs from that session's own documents. Every session's documents and vector
store are isolated from every other session's — there is no shared/global knowledge base.

## Setup

Activate the virtual environment (Windows PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

```bash
pip install -r requirements.txt
```

Copy `.env` and fill in:

```
OPENROUTER_API_KEY=...   # LLM (gpt-4o-mini) and embeddings via OpenRouter
SERPAPI_KEY=...           # Google Search via SerpAPI (web_search tool)
```

## Running

All commands from the project root.

**Backend** (FastAPI, port 8001):

```bash
python backend/api.py
```

**Frontend** (Vite, port 5173):

```bash
cd frontend && npm run dev
```

## Tests

```bash
pytest backend/tests/
```

## Architecture

```
Browser (frontend/index.html + chatbot.js)
    │ HTTP streaming  POST /chat  (session_id required)
    ▼
backend/api.py  (FastAPI)  → chatbot.chat_stream(session_id, query)
    ▼
backend/chatbot.py  ChatbotManager
    ├── Agent: LangGraph graph (worker → tools → evaluator loop) — tools in backend/tools.py
    ├── search_documents: queries ONLY the active session's own Chroma vector store
    │         (chroma_db/sessions/{session_id}/), populated from that session's uploads
    │         (documents/sessions/{session_id}/) — no global/shared document store
    └── Session history: SQLite (test_history.db)
```

| File | Purpose |
|---|---|
| `backend/api.py` | FastAPI app — POST /chat, /sessions, /history, /documents, /evaluate |
| `backend/chatbot.py` | ChatbotManager, LangGraph agent |
| `backend/tools.py` | LangChain tools: web_search, generate_presentation, generate_word_document, generate_pdf_document, search_documents |
| `backend/rag/rag_vector_db.py` | Per-session document embedding/deletion (`add_document_for_session`, `delete_document`) |
| `backend/rag/ragas_evaluator.py` | RAGAs-style evaluation of a session's document Q&A quality |

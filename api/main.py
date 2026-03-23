"""
FastAPI backend for the Webb AI Assistant.
"""

import os
import sys
import json
import time
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rag.query import answer, answer_stream

app = FastAPI(title="Webb AI Assistant")

# --- Rate limiting (simple in-memory, 20 requests per IP per minute) ---
RATE_LIMIT = 20
WINDOW_SECONDS = 60
request_counts = defaultdict(list)


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    timestamps = request_counts[ip]
    # Remove timestamps older than the window
    request_counts[ip] = [t for t in timestamps if now - t < WINDOW_SECONDS]
    if len(request_counts[ip]) >= RATE_LIMIT:
        return True
    request_counts[ip].append(now)
    return False


# --- Request/response models ---
class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


# --- Routes ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    ip = request.client.host
    if is_rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(body.question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 characters).")

    history = [{"role": m.role, "content": m.content} for m in body.history]

    try:
        result = answer(body.question, chat_history=history)
        return ChatResponse(answer=result["answer"], sources=result["sources"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating answer: {str(e)}")


@app.post("/api/chat/stream")
async def chat_stream(request: Request, body: ChatRequest):
    ip = request.client.host
    if is_rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(body.question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 characters).")

    history = [{"role": m.role, "content": m.content} for m in body.history]

    def event_generator():
        try:
            for event in answer_stream(body.question, chat_history=history):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Serve frontend ---
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))


# Mount at root last so API routes take priority
app.mount("/", StaticFiles(directory=frontend_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

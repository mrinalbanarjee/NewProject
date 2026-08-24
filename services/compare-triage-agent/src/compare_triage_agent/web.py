"""
FastAPI chat UI for the compare-triage-agent - a thin HTTP wrapper around
`agent.run_agent_turn`, so the web UI and the CLI share the exact same
tool-calling loop.

Conversation history is kept in-memory, keyed by a client-generated session
id (see static/app.js). That's fine for a single-process local demo; a real
deployment behind more than one worker or that needs to survive a restart
would need a shared store instead (Redis, a DB row) - the seam is
`_sessions`.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel

from compare_triage_agent.agent import run_agent_turn

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # services/compare-triage-agent
load_dotenv(_PACKAGE_ROOT / ".env")

app = FastAPI(title="compare-triage-agent")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

_client = genai.Client()
_sessions: dict[str, list[types.Content]] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class SessionRequest(BaseModel):
    session_id: str | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    conversation = _sessions.setdefault(session_id, [])

    conversation.append(types.Content(role="user", parts=[types.Part.from_text(text=request.message)]))
    try:
        reply = run_agent_turn(_client, conversation)
    except Exception as exc:  # noqa: BLE001 - surfaced to the chat UI, not a 500 the user can't act on
        conversation.pop()  # don't leave a dangling user turn the model never answered
        reply = f"Something went wrong talking to the model: {exc}"

    return ChatResponse(session_id=session_id, reply=reply)


@app.post("/api/reset", response_model=SessionRequest)
def reset(request: SessionRequest) -> SessionRequest:
    session_id = request.session_id or str(uuid.uuid4())
    _sessions.pop(session_id, None)
    return SessionRequest(session_id=session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("compare_triage_agent.web:app", host="127.0.0.1", port=8000, reload=True)

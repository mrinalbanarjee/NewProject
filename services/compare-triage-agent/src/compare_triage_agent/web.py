"""
FastAPI chat UI for the compare-triage-agent - a thin HTTP wrapper around
`agent.run_agent_turn`, so the web UI and the CLI share the exact same
tool-calling dispatcher.

Bring-your-own-token: the caller picks a provider (openai/google/anthropic)
and may supply their own API key per request. That key is used only to build
a client for that single request - it is never written to disk, logged, or
kept in `_sessions`. If no key is supplied, `agent.resolve_api_key` falls
back to the server's own .env for local-dev convenience.

Conversation history is kept in-memory, keyed by a client-generated session
id (see static/app.js), as a provider-neutral list of {role, content} turns -
see providers.py's docstring for why that's what makes switching providers
mid-session work. That in-memory store is fine for a single-process local
demo; a real deployment behind more than one worker or that needs to survive
a restart would need a shared store instead (Redis, a DB row).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from compare_triage_agent.agent import MissingApiKeyError, resolve_api_key, run_agent_turn
from compare_triage_agent.models import AccountDiagnostics
from compare_triage_agent.router import PROVIDERS, Provider

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]  # services/compare-triage-agent
load_dotenv(_PACKAGE_ROOT / ".env")

app = FastAPI(title="ALA Reconciliation Assistant")

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

_sessions: dict[str, list[dict]] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    provider: Provider = "google"
    api_key: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    model: str | None = None
    tier: str | None = None
    classification: list[AccountDiagnostics] | None = None
    mongo_script: str | None = None


class SessionRequest(BaseModel):
    session_id: str | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/api/providers")
def providers() -> list[str]:
    return list(PROVIDERS)


@app.post("/api/chat", response_model=ChatResponse, response_model_by_alias=True)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    history = _sessions.setdefault(session_id, [])

    try:
        api_key = resolve_api_key(request.provider, request.api_key)
        reply, model, tier, extras = run_agent_turn(request.provider, api_key, history, request.message)
    except MissingApiKeyError as exc:
        return ChatResponse(session_id=session_id, reply=str(exc))
    except Exception as exc:  # noqa: BLE001 - surfaced to the chat UI, not a 500 the user can't act on
        return ChatResponse(session_id=session_id, reply=f"Something went wrong talking to the model: {exc}")

    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": reply})
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        model=model,
        tier=tier,
        classification=extras.get("classification"),
        mongo_script=extras.get("mongo_script"),
    )


@app.post("/api/reset", response_model=SessionRequest)
def reset(request: SessionRequest) -> SessionRequest:
    session_id = request.session_id or str(uuid.uuid4())
    _sessions.pop(session_id, None)
    return SessionRequest(session_id=session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("compare_triage_agent.web:app", host="127.0.0.1", port=8000, reload=True)

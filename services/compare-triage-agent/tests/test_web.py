from __future__ import annotations

from fastapi.testclient import TestClient

from compare_triage_agent import providers
from compare_triage_agent.web import app

client = TestClient(app)


def test_index_serves_the_chat_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_providers_endpoint_lists_all_three():
    response = client.get("/api/providers")
    assert response.status_code == 200
    assert set(response.json()) == {"openai", "google", "anthropic"}


def test_chat_missing_api_key_reports_clearly(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.post("/api/chat", json={"message": "list mismatches", "provider": "google"})

    assert response.status_code == 200
    data = response.json()
    assert data["model"] is None
    assert "google" in data["reply"].lower()


def test_chat_success_roundtrip_returns_model_and_tier(monkeypatch):
    monkeypatch.setitem(
        providers.RUNNERS, "google", lambda api_key, model, history, message: ("Here are the mismatches.", {})
    )

    response = client.post(
        "/api/chat",
        json={"message": "list mismatches for ecn 6022768040250", "provider": "google", "api_key": "fake-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reply"] == "Here are the mismatches."
    assert data["model"] is not None
    assert data["tier"] == "fast"
    assert data["session_id"]
    assert data["classification"] is None
    assert data["mongo_script"] is None


def test_chat_surfaces_mongo_script_extra(monkeypatch):
    monkeypatch.setitem(
        providers.RUNNERS,
        "google",
        lambda api_key, model, history, message: (
            "Here's your script.",
            {"mongo_script": "db.customerevent.updateMany(...);"},
        ),
    )

    response = client.post(
        "/api/chat",
        json={"message": "generate the reprocess script", "provider": "google", "api_key": "fake-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mongo_script"] == "db.customerevent.updateMany(...);"


def test_chat_surfaces_classification_extra_as_camel_case(monkeypatch):
    fake_accounts = [
        {
            "ecn": "0444769043821",
            "accountNumber": "0580084955",
            "primaryCorrelationId": "44792fe1-4f9d-4693-b0e8-0e02f144d09e",
            "primarySucceeded": False,
            "primarySummary": "Duplicate boarding request received.",
            "diagnostics": [
                {
                    "correlationId": "CORR-DEP-1",
                    "requestMessageType": "OXCU305",
                    "eventTimestamp": "2026-08-19T01:21:20.295+00:00",
                    "failureReason": "Invalid phone number entered.",
                    "canBeReprocessed": False,
                    "recommendation": "Fix the phone number at the source system first.",
                }
            ],
        }
    ]
    monkeypatch.setitem(
        providers.RUNNERS,
        "google",
        lambda api_key, model, history, message: ("Here's the classification.", {"classification": fake_accounts}),
    )

    response = client.post(
        "/api/chat",
        json={"message": "check root cause for ACCOUNT_COMPARE on ecn 0444769043821", "provider": "google", "api_key": "fake-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["classification"]) == 1
    account = data["classification"][0]
    assert account["accountNumber"] == "0580084955"
    assert "account_number" not in account
    entry = account["diagnostics"][0]
    assert entry["correlationId"] == "CORR-DEP-1"
    assert "correlation_id" not in entry


def test_chat_persists_history_across_turns_in_the_same_session(monkeypatch):
    seen_histories = []

    def fake_runner(api_key, model, history, message):
        seen_histories.append(list(history))
        return f"reply to: {message}", {}

    monkeypatch.setitem(providers.RUNNERS, "google", fake_runner)

    first = client.post("/api/chat", json={"message": "first message", "provider": "google", "api_key": "fake-key"})
    session_id = first.json()["session_id"]

    client.post(
        "/api/chat",
        json={"message": "second message", "session_id": session_id, "provider": "google", "api_key": "fake-key"},
    )

    assert seen_histories[0] == []  # nothing yet on the first turn
    assert seen_histories[1] == [
        {"role": "user", "content": "first message"},
        {"role": "assistant", "content": "reply to: first message"},
    ]


def test_reset_clears_session_history(monkeypatch):
    monkeypatch.setitem(providers.RUNNERS, "google", lambda api_key, model, history, message: ("ok", {}))

    chat_response = client.post("/api/chat", json={"message": "hello", "provider": "google", "api_key": "fake-key"})
    session_id = chat_response.json()["session_id"]

    reset_response = client.post("/api/reset", json={"session_id": session_id})

    assert reset_response.status_code == 200
    assert reset_response.json()["session_id"] == session_id

    seen_histories = []
    monkeypatch.setitem(
        providers.RUNNERS,
        "google",
        lambda api_key, model, history, message: (seen_histories.append(list(history)) or "ok again", {}),
    )
    client.post("/api/chat", json={"message": "after reset", "session_id": session_id, "provider": "google", "api_key": "fake-key"})
    assert seen_histories[0] == []  # history was actually cleared, not just the endpoint returning 200

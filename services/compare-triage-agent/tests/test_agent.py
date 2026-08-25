from __future__ import annotations

import pytest

from compare_triage_agent import agent


def test_resolve_api_key_prefers_user_supplied_over_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "server-side-key")
    assert agent.resolve_api_key("google", "user-typed-key") == "user-typed-key"


def test_resolve_api_key_falls_back_to_env_when_not_supplied(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "server-side-key")
    assert agent.resolve_api_key("google", None) == "server-side-key"


def test_resolve_api_key_raises_when_neither_available(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(agent.MissingApiKeyError):
        agent.resolve_api_key("openai", None)


def test_missing_api_key_error_message_names_the_provider():
    err = agent.MissingApiKeyError("anthropic")
    assert "anthropic" in str(err)
    assert "ANTHROPIC_API_KEY" in str(err)


@pytest.mark.parametrize(
    "message",
    [
        "404 NOT_FOUND. model models/gemini-2.5-flash is no longer available",
        "The model `gpt-9000` does not exist",
        "Unknown model: claude-nonexistent",
    ],
)
def test_looks_like_model_not_found_recognizes_common_provider_phrasings(message):
    assert agent._looks_like_model_not_found(Exception(message))


def test_looks_like_model_not_found_does_not_misfire_on_unrelated_errors():
    assert not agent._looks_like_model_not_found(Exception("Your credit balance is too low"))
    assert not agent._looks_like_model_not_found(Exception("Connection timed out"))


def test_run_agent_turn_retries_on_fast_tier_when_reasoning_model_not_found(monkeypatch):
    calls = []

    def fake_runner(api_key, model, history, user_message):
        calls.append(model)
        if len(calls) == 1:
            raise Exception("model gemini-3.6-pro is not found")
        return "ok", {}

    monkeypatch.setitem(agent.RUNNERS, "google", fake_runner)

    reply, model, tier, extras = agent.run_agent_turn("google", "key", [], "why did this account fail to board?")

    assert reply == "ok"
    assert tier == "reasoning"
    assert extras == {}
    assert len(calls) == 2
    assert calls[1] == agent.router.resolve_model("google", "fast")
    assert model == calls[1]


def test_run_agent_turn_surfaces_extras_from_the_runner(monkeypatch):
    monkeypatch.setitem(
        agent.RUNNERS, "google", lambda api_key, model, history, user_message: ("here's your script", {"mongo_script": "db.customerevent.updateMany(...)"})
    )

    reply, model, tier, extras = agent.run_agent_turn("google", "key", [], "generate the script")

    assert extras == {"mongo_script": "db.customerevent.updateMany(...)"}


def test_run_agent_turn_does_not_retry_fast_tier_failures(monkeypatch):
    def fake_runner(api_key, model, history, user_message):
        raise Exception("model not found")

    monkeypatch.setitem(agent.RUNNERS, "google", fake_runner)

    with pytest.raises(Exception):
        agent.run_agent_turn("google", "key", [], "list all mismatches")


def test_run_agent_turn_does_not_swallow_unrelated_errors(monkeypatch):
    def fake_runner(api_key, model, history, user_message):
        raise Exception("insufficient_quota: credit balance too low")

    monkeypatch.setitem(agent.RUNNERS, "google", fake_runner)

    with pytest.raises(Exception, match="insufficient_quota"):
        agent.run_agent_turn("google", "key", [], "why did this account fail to board?")

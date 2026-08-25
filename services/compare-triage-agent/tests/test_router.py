from __future__ import annotations

import pytest

from compare_triage_agent import router


@pytest.mark.parametrize(
    "text",
    [
        "List everything that doesn't match between Hogan and Alfa.",
        "What all doesn't match for ecn 6022768040250?",
        "Show me the compare mismatches for ecn 5021410435426",
    ],
)
def test_classify_query_flat_lookups_are_fast_tier(text):
    assert router.classify_query(text) == "fast"


@pytest.mark.parametrize(
    "text",
    [
        "Check the root cause for ACCOUNT_COMPARE on ecn 0444769043821.",
        "Why did this account fail to board?",
        "Can you explain how to resolve this dependent failure?",
        "Walk me through the boarding issue for this ECN.",
        "How do I fix this ACCOUNT_COMPARE mismatch?",
    ],
)
def test_classify_query_investigations_are_reasoning_tier(text):
    assert router.classify_query(text) == "reasoning"


def test_classify_query_is_case_insensitive():
    assert router.classify_query("WHY IS THIS ACCOUNT FAILING?") == "reasoning"


def test_resolve_model_returns_a_default_for_every_provider_and_tier():
    for provider in router.PROVIDERS:
        for tier in ("fast", "reasoning"):
            model = router.resolve_model(provider, tier)
            assert isinstance(model, str) and model


def test_resolve_model_fast_and_reasoning_defaults_differ():
    for provider in router.PROVIDERS:
        assert router.resolve_model(provider, "fast") != router.resolve_model(provider, "reasoning")


def test_resolve_model_env_override_wins(monkeypatch):
    monkeypatch.setenv("GOOGLE_FAST_MODEL", "gemini-custom-test-model")
    assert router.resolve_model("google", "fast") == "gemini-custom-test-model"

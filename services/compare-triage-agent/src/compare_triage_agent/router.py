"""
Picks which model tier a query needs, and resolves that tier to an actual
model id for whichever provider the user selected.

Two tiers, not a full classifier LLM call: this assistant only really has two
shapes of question (a flat lookup vs. a multi-step root-cause investigation
that chains a tool call, cross-references timestamps, and narrates a
resolution), so a fast keyword check is enough to route between them without
spending an extra model round-trip - and every extra round-trip is extra
latency and cost on someone's own API key.
"""

from __future__ import annotations

import os
from typing import Literal

Tier = Literal["fast", "reasoning"]
Provider = Literal["openai", "google", "anthropic"]

PROVIDERS: tuple[Provider, ...] = ("openai", "google", "anthropic")

# Anything that smells like "explain why" or "walk me through the root cause"
# needs the multi-step tool-call -> cross-reference -> narrate-a-resolution
# path, not a flat lookup.
_REASONING_TRIGGERS = (
    "root cause",
    "root-cause",
    "rootcause",
    "why",
    "resolve",
    "resolution",
    "diagnose",
    "diagnosis",
    "explain",
    "account_compare",
    "dependent failure",
    "boarding",
    "how do i fix",
    "how to fix",
    "how can i fix",
    "walk me through",
)


def classify_query(text: str) -> Tier:
    lowered = text.lower()
    if any(trigger in lowered for trigger in _REASONING_TRIGGERS):
        return "reasoning"
    return "fast"


# Defaults as of when this was wired up - a model going stale (renamed,
# retired, replaced) is expected over time, which is exactly why every one of
# these is also overridable via env var, and why the dispatcher in agent.py
# retries once on the fast-tier model if a provider reports the tier model
# doesn't exist.
_DEFAULT_MODELS: dict[tuple[Provider, Tier], str] = {
    ("openai", "fast"): "gpt-4o-mini",
    ("openai", "reasoning"): "gpt-4o",
    ("google", "fast"): "gemini-3.6-flash",
    ("google", "reasoning"): "gemini-3.6-pro",
    ("anthropic", "fast"): "claude-haiku-4-5-20251001",
    ("anthropic", "reasoning"): "claude-sonnet-5",
}

_ENV_OVERRIDES: dict[tuple[Provider, Tier], str] = {
    ("openai", "fast"): "OPENAI_FAST_MODEL",
    ("openai", "reasoning"): "OPENAI_REASONING_MODEL",
    ("google", "fast"): "GOOGLE_FAST_MODEL",
    ("google", "reasoning"): "GOOGLE_REASONING_MODEL",
    ("anthropic", "fast"): "ANTHROPIC_FAST_MODEL",
    ("anthropic", "reasoning"): "ANTHROPIC_REASONING_MODEL",
}


def resolve_model(provider: Provider, tier: Tier) -> str:
    env_name = _ENV_OVERRIDES[(provider, tier)]
    return os.environ.get(env_name) or _DEFAULT_MODELS[(provider, tier)]


def looks_like_model_not_found(exc: Exception) -> bool:
    """Shared by every caller that resolves a tier to a model id and then actually
    calls a provider with it (agent.py's chat loop, classifier.py's structured
    classification call) - a model going stale (renamed, retired) is a real,
    recurring failure mode here, not a hypothetical one, so every such caller
    retries once on the fast tier rather than failing the whole request."""
    text = str(exc).lower()
    return "model" in text and any(
        phrase in text for phrase in ("not found", "not_found", "no longer available", "does not exist", "unknown model")
    )

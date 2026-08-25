"""
Top-level entry point: pick a model tier for the query, resolve an API key,
run that provider's tool-calling loop, and retry once on the fast tier if the
provider says the chosen model doesn't exist (a model going stale - renamed,
retired - is a real, recurring failure mode, not a hypothetical one).
"""

from __future__ import annotations

import os

from compare_triage_agent import router
from compare_triage_agent.providers import RUNNERS
from compare_triage_agent.router import Provider

_PROVIDER_ENV_KEYS: dict[Provider, str] = {
    "openai": "OPENAI_API_KEY",
    "google": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class MissingApiKeyError(Exception):
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        super().__init__(
            f"No API key for {provider}. Enter your own key in the chat UI, or set "
            f"{_PROVIDER_ENV_KEYS[provider]} on the server."
        )


def resolve_api_key(provider: Provider, user_supplied: str | None) -> str:
    """BYOT first - a key typed into the chat UI always wins - falling back to the
    server's own .env for local-dev convenience only when the user didn't supply one."""
    if user_supplied:
        return user_supplied
    value = os.environ.get(_PROVIDER_ENV_KEYS[provider])
    if not value:
        raise MissingApiKeyError(provider)
    return value


_looks_like_model_not_found = router.looks_like_model_not_found


def run_agent_turn(
    provider: Provider, api_key: str, history: list[dict], user_message: str
) -> tuple[str, str, str, dict]:
    """Runs one user turn to completion. Returns (reply_text, model_actually_used, tier, extras).

    `extras` carries the raw classify_account_compare_failures / generate_reprocess_script
    tool result for this turn, if either was called (see providers.py) - the chat UI uses
    it to render an interactive checkbox picker / a copyable script block. Empty dict if
    neither tool ran.

    `history` is read, never mutated - the caller decides what to persist
    (see providers.py's module docstring for why: it lets a session carry
    context across a mid-conversation provider switch).
    """
    runner = RUNNERS[provider]
    tier = router.classify_query(user_message)
    model = router.resolve_model(provider, tier)

    try:
        reply, extras = runner(api_key, model, history, user_message)
    except Exception as exc:
        if tier == "fast" or not _looks_like_model_not_found(exc):
            raise
        fallback_model = router.resolve_model(provider, "fast")
        reply, extras = runner(api_key, fallback_model, history, user_message)
        model = fallback_model

    return reply, model, tier, extras

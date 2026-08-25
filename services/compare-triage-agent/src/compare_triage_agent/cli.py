"""Interactive REPL entry point: `python -m compare_triage_agent.cli`."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from compare_triage_agent.agent import resolve_api_key, run_agent_turn
from compare_triage_agent.router import PROVIDERS


def main() -> None:
    load_dotenv()
    provider = os.environ.get("COMPARE_AGENT_PROVIDER", "google")
    if provider not in PROVIDERS:
        raise SystemExit(f"COMPARE_AGENT_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    api_key = resolve_api_key(provider, os.environ.get("COMPARE_AGENT_API_KEY"))
    history: list[dict] = []

    print(f"ALA Reconciliation Assistant (provider: {provider}). Ctrl+C to exit.\n")
    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not user_input:
            continue

        try:
            answer, model, tier, extras = run_agent_turn(provider, api_key, history, user_input)
        except Exception as exc:  # noqa: BLE001 - keep the REPL alive on a bad turn
            print(f"\n[error] {exc}\n")
            continue

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": answer})
        print(f"\n[{model} - {tier}] {answer}\n")
        if extras.get("mongo_script"):
            print(f"--- mongo script ---\n{extras['mongo_script']}\n--------------------\n")


if __name__ == "__main__":
    main()

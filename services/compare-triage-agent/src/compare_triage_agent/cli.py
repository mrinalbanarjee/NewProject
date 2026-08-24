"""Interactive REPL entry point: `python -m compare_triage_agent.cli`."""

from __future__ import annotations

from google import genai
from google.genai import types
from dotenv import load_dotenv

from compare_triage_agent.agent import run_agent_turn


def main() -> None:
    load_dotenv()
    client = genai.Client()
    conversation: list[types.Content] = []

    print("Customer sync triage agent. Ask about compare mismatches or ACCOUNT_COMPARE root cause. Ctrl+C to exit.\n")
    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not user_input:
            continue

        conversation.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))
        try:
            answer = run_agent_turn(client, conversation)
        except Exception as exc:  # noqa: BLE001 - keep the REPL alive on a bad turn
            print(f"\n[error] {exc}\n")
            conversation.pop()
            continue

        print(f"\n{answer}\n")


if __name__ == "__main__":
    main()

"""
One tool-calling turn-runner per provider SDK, all with the same signature:

    run_turn(api_key: str, model: str, history: list[dict], user_message: str) -> tuple[str, dict]

`history` is the provider-neutral transcript kept by the caller - a plain
list of {"role": "user" | "assistant", "content": str} turns, with none of
the intra-turn tool-call scaffolding persisted. That's what makes a session
portable across providers (switch from Gemini to Claude mid-conversation and
the new provider still gets full prior context): each SDK's tool-use dance
only has to survive for the one turn it's running, then collapses back down
to a plain text reply before being handed back to the caller.

The second return value ("extras") surfaces the raw result of two kinds of
tool call - classify_account_compare_failures, and *any* tool whose result
carries a "script" key (generate_reprocess_script, generate_config_update_script,
and anything added later) - so the chat UI can render an interactive checkbox
picker / a copyable script block instead of parsing them back out of the
model's prose. Only ever the *last* occurrence of each within the turn is kept
(a turn calling either kind twice would be unusual, and only the latest result
is what the reply actually narrates). Everything else about the turn - the
plain data tools - only ever reaches the model as text, same as before.

None of these functions mutate `history` - the caller decides what to persist.
"""

from __future__ import annotations

import json

from compare_triage_agent.prompts import SYSTEM_PROMPT
from compare_triage_agent.toolset import TOOL_DEFINITIONS, dispatch_tool

_CLASSIFY_TOOL = "classify_account_compare_failures"


def _capture_extras(name: str, result: object, extras: dict) -> None:
    if name == _CLASSIFY_TOOL and isinstance(result, dict) and result.get("found") and result.get("accounts"):
        extras["classification"] = result["accounts"]
    elif isinstance(result, dict) and "script" in result:
        extras["mongo_script"] = result["script"]


def _run_openai_turn(api_key: str, model: str, history: list[dict], user_message: str) -> tuple[str, dict]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOL_DEFINITIONS
    ]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": turn["role"], "content": turn["content"]} for turn in history)
    messages.append({"role": "user", "content": user_message})
    extras: dict = {}

    while True:
        response = client.chat.completions.create(model=model, messages=messages, tools=tools)
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or "", extras

        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                result = dispatch_tool(call.function.name, args, provider="openai", api_key=api_key)
                _capture_extras(call.function.name, result, extras)
                content = json.dumps({"result": result})
            except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not raised
                content = json.dumps({"error": str(exc)})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})


def _run_gemini_turn(api_key: str, model: str, history: list[dict], user_message: str) -> tuple[str, dict]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["input_schema"])
            for t in TOOL_DEFINITIONS
        ]
    )
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=[tool])

    contents = [
        types.Content(role="model" if turn["role"] == "assistant" else "user", parts=[types.Part.from_text(text=turn["content"])])
        for turn in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
    extras: dict = {}

    while True:
        response = client.models.generate_content(model=model, contents=contents, config=config)
        contents.append(response.candidates[0].content)

        if not response.function_calls:
            return response.text or "", extras

        response_parts = []
        for call in response.function_calls:
            try:
                result = dispatch_tool(call.name, call.args or {}, provider="google", api_key=api_key)
                _capture_extras(call.name, result, extras)
                function_response = {"result": result}
            except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not raised
                function_response = {"error": str(exc)}
            response_parts.append(types.Part.from_function_response(name=call.name, response=function_response))
        contents.append(types.Content(role="user", parts=response_parts))


def _run_anthropic_turn(api_key: str, model: str, history: list[dict], user_message: str) -> tuple[str, dict]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
    messages.append({"role": "user", "content": user_message})
    extras: dict = {}

    while True:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text"), extras

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = dispatch_tool(block.name, block.input, provider="anthropic", api_key=api_key)
                _capture_extras(block.name, result, extras)
                content = json.dumps(result)
                is_error = False
            except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not raised
                content = str(exc)
                is_error = True
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": tool_results})


RUNNERS = {
    "openai": _run_openai_turn,
    "google": _run_gemini_turn,
    "anthropic": _run_anthropic_turn,
}

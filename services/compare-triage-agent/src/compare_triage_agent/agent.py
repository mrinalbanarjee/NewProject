"""
Tool-calling loop around the Gemini API (`google-genai`).

Kept deliberately thin: the model decides which tool(s) to call and how to
narrate the result, this module just executes whatever it asks for against
`tools.TOOL_DEFINITIONS` / `tools.dispatch_tool` and feeds the result back
until the model produces a final text answer.
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types

from compare_triage_agent.tools import TOOL_DEFINITIONS, dispatch_tool

DEFAULT_MODEL = os.environ.get("COMPARE_AGENT_MODEL", "gemini-3.6-flash")

SYSTEM_PROMPT = """\
You help operators investigate Hogan/Alfa customer-sync issues.

Two tools are available:
- list_customer_compare_mismatches: any attribute mismatch, any keyName.
- get_account_compare_root_cause: root-causes ACCOUNT_COMPARE mismatches only \
(Hogan account boarding status + downstream dependent failures that happened \
after it).

Rules:
- If the user asks for mismatches in general, call list_customer_compare_mismatches \
and summarize the results clearly - group by ECN, call out the keyName and the \
Hogan-vs-Alfa values from each comment.
- If the user asks for root cause of a specific mismatch category, only \
ACCOUNT_COMPARE is currently supported. If they ask about another category \
(PHONE_COMPARE, ADDRESS_COMPARE, NAME_COMPARE, etc.), say plainly that root-cause \
lookup for that category isn't available yet - don't call the tool for it.
- For ACCOUNT_COMPARE root cause, call get_account_compare_root_cause and then, for \
each account, present: the primary boarding status (succeeded/failed, its summary, \
event time), then every dependent failure in chronological order (its update type, \
description, event time), and a short plain-English read on what likely needs to \
happen to resolve it (e.g. a failed boarding status means the account needs to board \
successfully before any of the dependent customer maintenance failures can be \
expected to clear).
- The tool output is already written in plain English with internal system codes and \
GUIDs stripped out - present update_type, summary, and description text as-is. Never \
mention, invent, or ask about a code like OXCU200E, 0XCA015E, a correlation GUID, or \
any other internal identifier - none of that belongs in front of this audience.
- Write field values as prose, not as field_name: value pairs - e.g. say "Boarding \
failed" or "Boarding succeeded", never echo the literal field name `succeeded` or a \
raw `true`/`false`.
- If a lookup returns nothing, say so plainly rather than guessing.
- Be concise but complete - this is an operational triage response, not prose.
"""

_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters_json_schema=tool["input_schema"],
        )
        for tool in TOOL_DEFINITIONS
    ]
)

_CONFIG = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=[_TOOLS])


def run_agent_turn(client: genai.Client, conversation: list[types.Content], model: str = DEFAULT_MODEL) -> str:
    """Runs one user turn to completion (including any tool round-trips) and returns the final assistant text."""
    while True:
        response = client.models.generate_content(model=model, contents=conversation, config=_CONFIG)

        conversation.append(response.candidates[0].content)

        if not response.function_calls:
            return response.text or ""

        response_parts = []
        for call in response.function_calls:
            try:
                result = dispatch_tool(call.name, call.args or {})
                function_response = {"result": result}
            except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not raised
                function_response = {"error": str(exc)}
            response_parts.append(types.Part.from_function_response(name=call.name, response=function_response))

        conversation.append(types.Content(role="user", parts=response_parts))

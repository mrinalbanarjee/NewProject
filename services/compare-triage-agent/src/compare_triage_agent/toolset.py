"""
The full tool registry the chat agent dispatches against - `tools.py`'s plain
data lookups, `config_tools.py`'s app-config get/update-script tools, plus two
more tools that need things a plain dispatch_tool deliberately doesn't have
access to:

- classify_account_compare_failures needs an LLM call of its own (classifier.py's
  forced-JSON-schema classification), so it needs the *current* provider/api_key.
- generate_reprocess_script is pure templating (reprocess.py), no LLM needed,
  but it's naturally paired with the classify tool so both live here.

Kept out of tools.py to avoid a tools.py <-> classifier.py import cycle -
classifier.py already imports get_account_compare_root_cause from tools.py.
"""

from __future__ import annotations

from typing import Any

from compare_triage_agent import classifier, config_tools, reprocess, tools
from compare_triage_agent.router import Provider

CLASSIFY_TOOL_DEFINITION: dict[str, Any] = {
    "name": "classify_account_compare_failures",
    "description": (
        "For an ECN's mismatched ACCOUNT_COMPARE account(s), classifies each dependent "
        "failure as reprocessable (canBeReprocessed:true - collateral damage from the "
        "account not being boarded yet in Hogan; will likely clear once the primary "
        "boarding issue is fixed) or not (canBeReprocessed:false - the payload itself is "
        "bad/invalid/missing a field; reprocessing without a source-data fix will fail "
        "again). Only call this when the user is specifically asking about reprocessing "
        "or a reprocess recommendation - for a plain root-cause question, use "
        "get_account_compare_root_cause instead, which returns the same primary boarding "
        "status and dependent failures without the classification step. Every diagnostics "
        "entry keeps its correlationId - never drop or paraphrase those, the user needs "
        "the exact id to select it and you need it to build a reprocess script afterward. "
        "If a returned account has zero diagnostics entries, it has no dependent failures "
        "to classify - say so, don't invent any. If the result is an object with "
        "found:false, no matching ACCOUNT_COMPARE mismatch exists for that ecn/account_number."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ecn": {"type": "string", "description": "Enterprise Customer Number."},
            "account_number": {
                "type": "string",
                "description": "Optional. Scope to one specific mismatched account under the ECN; omit to classify every mismatched ACCOUNT_COMPARE account for that ECN.",
            },
        },
        "required": ["ecn"],
    },
}

GENERATE_SCRIPT_TOOL_DEFINITION: dict[str, Any] = {
    "name": "generate_reprocess_script",
    "description": (
        "Builds the targeted Mongo shell reprocess script for a set of correlationIds "
        "the user has chosen to reprocess - call this once the user has told you which "
        "failures to reprocess (by naming correlationIds directly, or by accepting your "
        "canBeReprocessed:true recommendations from classify_account_compare_failures - "
        "in that case, pass the exact correlationIds of the ones they accepted). Include "
        "the account's primary boarding correlationId whenever you have it and the user "
        "hasn't said not to - the dependent messages generally won't succeed until the "
        "account itself is reprocessed/reboarded too. Never call this with correlationIds "
        "you weren't given by an earlier tool result or by the user - don't invent one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "primary_correlation_id": {
                "type": "string",
                "description": "The account's primary boarding correlationId, if known and applicable. Omit if there isn't one or the user asked to exclude it.",
            },
            "selected_correlation_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "correlationIds of the dependent failures to reprocess.",
            },
        },
        "required": ["selected_correlation_ids"],
    },
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    *tools.TOOL_DEFINITIONS,
    CLASSIFY_TOOL_DEFINITION,
    GENERATE_SCRIPT_TOOL_DEFINITION,
    *config_tools.TOOL_DEFINITIONS,
]

_CONFIG_TOOL_NAMES = {"get_app_config_value", "generate_config_update_script"}


def dispatch_tool(name: str, tool_input: dict[str, Any], *, provider: Provider, api_key: str) -> Any:
    if name in _CONFIG_TOOL_NAMES:
        return config_tools.dispatch_tool(name, tool_input)

    if name == "classify_account_compare_failures":
        ecn = tool_input["ecn"]
        account_number = tool_input.get("account_number")
        if not tools.ecn_exists(ecn):
            return {"found": False, "message": f"No compare record found for ECN '{ecn}'."}

        accounts = classifier.classify_ecn(provider, api_key, ecn, account_number)
        if not accounts:
            scope = f"account '{account_number}'" if account_number else "any account"
            return {"found": False, "message": f"No ACCOUNT_COMPARE mismatch found for ECN '{ecn}' and {scope}."}
        return {"found": True, "accounts": [a.model_dump(by_alias=True) for a in accounts]}

    if name == "generate_reprocess_script":
        try:
            script = reprocess.build_reprocess_script(
                tool_input.get("primary_correlation_id"), tool_input.get("selected_correlation_ids", [])
            )
        except ValueError as exc:
            return {"error": str(exc)}
        return {"script": script}

    return tools.dispatch_tool(name, tool_input)

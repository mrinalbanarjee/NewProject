"""
Classifies each dependent failure on an account as either a Collateral /
Dependency Failure (canBeReprocessed: true - it's downstream fallout from the
account not being boarded yet, and should clear on its own once boarding is
fixed) or an Inherent Data Validation Failure (canBeReprocessed: false - the
payload itself is bad and reprocessing without a source-data fix will just
fail again).

This is a genuine judgment call, not a fixed code lookup, so it's delegated to
the LLM - but the shape of the answer is fixed, so every provider is forced
into that exact JSON schema (OpenAI: response_format=json_schema; Gemini:
response_json_schema; Anthropic has no native JSON-schema response mode, so
it's forced via a single tool with tool_choice pinned to it) rather than
trusted to follow a prose instruction.
"""

from __future__ import annotations

import json

from compare_triage_agent.models import AccountDiagnostics, AccountRootCause, DiagnosticsResult
from compare_triage_agent.router import Provider, looks_like_model_not_found, resolve_model
from compare_triage_agent.tools import get_account_compare_root_cause

CLASSIFICATION_CRITERIA = """\
Classify each customer-sync failure below into exactly one of two categories. Return \
one diagnostics entry per failure given, in the same order, using the required schema.

Category -> canBeReprocessed: true (Collateral / Dependency Failure)
The failure occurred because the account/customer record was not yet active or \
boarded in Hogan (e.g., "ACCOUNT NOT FOUND", "RELATIONSHIP CODE CONFLICT", "RECORD \
LOCKED", "TIMEOUT"). Once the primary boarding issue is fixed, reprocessing this \
message will succeed.

Category -> canBeReprocessed: false (Inherent Data Validation Failure)
The failure is due to malformed, invalid, or missing payload fields (e.g., "INVALID \
AREA CODE", "INVALID SSN/TAX ID", "MISSING POSTAL CODE"). Reprocessing without data \
correction at source will fail again.

Use the primary boarding status below as context: if it failed, a dependent failure \
is more likely collateral damage from that - but only mark canBeReprocessed:true when \
the failure text itself is consistent with being blocked by the account/boarding \
state, not just because boarding happened to also fail. A failure whose own text \
plainly names a bad/invalid/missing field is an Inherent Data Validation Failure \
(canBeReprocessed:false) regardless of the boarding outcome.
"""

DIAGNOSTICS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnostics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "correlationId": {"type": "string"},
                    "requestMessageType": {"type": "string"},
                    "eventTimestamp": {"type": "string"},
                    "failureReason": {
                        "type": "string",
                        "description": "One-sentence plain-English restatement of why this specific failure happened.",
                    },
                    "canBeReprocessed": {"type": "boolean"},
                    "recommendation": {
                        "type": "string",
                        "description": "One sentence telling the operator what to do about this specific failure.",
                    },
                },
                "required": [
                    "correlationId",
                    "requestMessageType",
                    "eventTimestamp",
                    "failureReason",
                    "canBeReprocessed",
                    "recommendation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["diagnostics"],
    "additionalProperties": False,
}


def _build_prompt(account: AccountRootCause) -> str:
    boarding = account.primary_boarding_status
    if boarding:
        boarding_context = f"Primary boarding status for account {account.account_number}: {boarding.summary} (succeeded={boarding.succeeded})"
    else:
        boarding_context = f"No Hogan boarding record was found at all for account {account.account_number}."

    failures = [
        {
            "correlationId": f.correlation_id,
            "requestMessageType": f.raw_request_message_type,
            "eventTimestamp": f.event_time_stamp,
            "description": f.description,
        }
        for f in account.dependent_failures
    ]

    return (
        f"{CLASSIFICATION_CRITERIA}\n"
        f"{boarding_context}\n\n"
        f"Failures to classify:\n{json.dumps(failures, indent=2)}"
    )


def _classify_openai(api_key: str, model: str, prompt: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "diagnostics", "schema": DIAGNOSTICS_JSON_SCHEMA, "strict": True},
        },
    )
    return json.loads(response.choices[0].message.content)


def _classify_gemini(api_key: str, model: str, prompt: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=DIAGNOSTICS_JSON_SCHEMA,
        ),
    )
    return json.loads(response.text)


def _classify_anthropic(api_key: str, model: str, prompt: str) -> dict:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        tools=[
            {
                "name": "emit_diagnostics",
                "description": "Return the classification result for every failure given.",
                "input_schema": DIAGNOSTICS_JSON_SCHEMA,
            }
        ],
        tool_choice={"type": "tool", "name": "emit_diagnostics"},
    )
    tool_block = next(block for block in response.content if block.type == "tool_use")
    return tool_block.input


_CLASSIFIERS = {
    "openai": _classify_openai,
    "google": _classify_gemini,
    "anthropic": _classify_anthropic,
}


def classify_account(provider: Provider, api_key: str, account: AccountRootCause) -> AccountDiagnostics:
    boarding = account.primary_boarding_status
    primary_fields = dict(
        primaryCorrelationId=boarding.correlation_id if boarding else None,
        primarySucceeded=boarding.succeeded if boarding else None,
        primarySummary=boarding.summary if boarding else None,
    )

    if not account.dependent_failures:
        return AccountDiagnostics(ecn=account.ecn, accountNumber=account.account_number, diagnostics=[], **primary_fields)

    model = resolve_model(provider, "reasoning")
    prompt = _build_prompt(account)
    try:
        raw = _CLASSIFIERS[provider](api_key, model, prompt)
    except Exception as exc:
        if not looks_like_model_not_found(exc):
            raise
        model = resolve_model(provider, "fast")
        raw = _CLASSIFIERS[provider](api_key, model, prompt)
    result = DiagnosticsResult.model_validate(raw)

    return AccountDiagnostics(
        ecn=account.ecn, accountNumber=account.account_number, diagnostics=result.diagnostics, **primary_fields
    )


def classify_ecn(provider: Provider, api_key: str, ecn: str, account_number: str | None = None) -> list[AccountDiagnostics]:
    """One classification pass per mismatched ACCOUNT_COMPARE account under the ECN
    (or just the one account, if account_number narrows it down)."""
    accounts = get_account_compare_root_cause(ecn=ecn, account_number=account_number)
    return [classify_account(provider, api_key, account) for account in accounts]

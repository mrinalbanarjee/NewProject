"""
The two tools the agent can call.

- `list_customer_compare_mismatches` answers "what's not matching between Hogan
  and Alfa" straight from the compare-results export.
- `get_account_compare_root_cause` is scoped to ACCOUNT_COMPARE only (per current
  requirements - PHONE_COMPARE etc. aren't wired up yet). It joins a mismatched
  account back to its Hogan boarding response, then pulls FailureListResponse
  entries for that same (ecn, accountNumber) whose eventTimeStamp falls *after*
  the boarding response's eventTime - those are the downstream failures the
  boarding problem produced, not unrelated noise from before it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from compare_triage_agent.data_sources import load_boarding_status, load_compare_results, load_failure_list
from compare_triage_agent.message_catalog import describe_request_message_type, humanize_boarding_text, humanize_response_text
from compare_triage_agent.models import AccountRootCause, BoardingStatus, CustomerMismatch, DependentFailure, MismatchAttribute


def _parse_iso8601(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def list_customer_compare_mismatches(ecn: str | None = None) -> list[CustomerMismatch]:
    results: list[CustomerMismatch] = []
    for record in load_compare_results():
        if ecn and record["ecn"] != ecn:
            continue
        mismatches = [
            MismatchAttribute(
                field_name=attr["fieldName"],
                key_name=attr["keyName"],
                comment=attr.get("comment", ""),
                account_number=attr.get("accountNumber"),
                is_cuac_code_matched=attr.get("isCuacCodeMatched"),
            )
            for attr in record["attributes"]
            if not attr["isMatched"]
        ]
        if mismatches:
            results.append(
                CustomerMismatch(
                    ecn=record["ecn"],
                    third_party_number=record["thirdPartyNumber"],
                    mismatches=mismatches,
                )
            )
    return results


def get_account_compare_root_cause(ecn: str, account_number: str | None = None) -> list[AccountRootCause]:
    record = next((r for r in load_compare_results() if r["ecn"] == ecn), None)
    if record is None:
        return []

    mismatched_accounts = [
        attr
        for attr in record["attributes"]
        if attr["keyName"] == "ACCOUNT_COMPARE"
        and not attr["isMatched"]
        and (account_number is None or attr.get("accountNumber") == account_number)
    ]
    if not mismatched_accounts:
        return []

    boarding_by_account = {b["accountNumber"]: b for b in load_boarding_status()}
    failure_records = load_failure_list()

    results: list[AccountRootCause] = []
    for attr in mismatched_accounts:
        acct = attr["accountNumber"]
        boarding = boarding_by_account.get(acct)

        primary_status: BoardingStatus | None = None
        boarding_event_time: datetime | None = None
        if boarding:
            summary, succeeded = humanize_boarding_text(boarding["loanBoardingText"])
            primary_status = BoardingStatus(
                account_number=boarding["accountNumber"],
                succeeded=succeeded,
                summary=summary,
                event_time=boarding["eventTime"],
            )
            boarding_event_time = _parse_iso8601(boarding["eventTime"])

        dependent_failures: list[DependentFailure] = []
        for failure_record in failure_records:
            if failure_record["ecn"] != ecn or failure_record["accountNumber"] != acct:
                continue
            for entry in failure_record["failures"]:
                event_time = _parse_iso8601(entry["eventTimeStamp"])
                if boarding_event_time is not None and event_time <= boarding_event_time:
                    continue
                dependent_failures.append(
                    DependentFailure(
                        correlation_id=entry["correlationId"],
                        update_type=describe_request_message_type(entry["requestMessageType"]),
                        description=humanize_response_text(entry["responseText"]),
                        event_time_stamp=entry["eventTimeStamp"],
                    )
                )
        dependent_failures.sort(key=lambda d: d.event_time_stamp)

        results.append(
            AccountRootCause(
                ecn=ecn,
                account_number=acct,
                compare_comment=attr.get("comment", ""),
                is_cuac_code_matched=attr.get("isCuacCodeMatched"),
                primary_boarding_status=primary_status,
                dependent_failures=dependent_failures,
            )
        )
    return results


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_customer_compare_mismatches",
        "description": (
            "List every attribute that does NOT match between Hogan and Alfa for a customer "
            "compare run. Omit ecn to get mismatches across all customers in the compare batch; "
            "pass ecn to scope to one customer. Each returned attribute includes its keyName "
            "(e.g. ACCOUNT_COMPARE, PHONE_COMPARE, ADDRESS_COMPARE) so the caller can decide "
            "whether a root-cause lookup is available for that category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ecn": {
                    "type": "string",
                    "description": "Enterprise Customer Number to scope the mismatch list to a single customer. Omit for all customers.",
                }
            },
        },
    },
    {
        "name": "get_account_compare_root_cause",
        "description": (
            "Root-cause a ACCOUNT_COMPARE mismatch for one ECN. Only ACCOUNT_COMPARE is "
            "supported right now - do not call this for other keyName categories (PHONE_COMPARE, "
            "ADDRESS_COMPARE, etc.), tell the user those aren't supported yet instead. Returns, "
            "per mismatched account: the Hogan account boarding status (the primary failure), and "
            "every FailureListResponse entry for that same ecn+account whose event time is after "
            "the boarding response - i.e. the downstream failures caused by the boarding problem. "
            "All text fields are already plain-English summaries with internal codes/GUIDs stripped "
            "out - present them as-is rather than looking for or inventing technical codes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ecn": {"type": "string", "description": "Enterprise Customer Number."},
                "account_number": {
                    "type": "string",
                    "description": "Optional. Scope to one specific mismatched account under the ECN; omit to get all mismatched ACCOUNT_COMPARE accounts for that ECN.",
                },
            },
            "required": ["ecn"],
        },
    },
]


def dispatch_tool(name: str, tool_input: dict[str, Any]) -> Any:
    if name == "list_customer_compare_mismatches":
        result = list_customer_compare_mismatches(ecn=tool_input.get("ecn"))
    elif name == "get_account_compare_root_cause":
        result = get_account_compare_root_cause(
            ecn=tool_input["ecn"], account_number=tool_input.get("account_number")
        )
    else:
        raise ValueError(f"Unknown tool: {name}")

    return [item.model_dump() for item in result]

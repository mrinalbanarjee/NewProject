"""
Feature Management: get/update tools for the LoanBoarding, CustomerSync, and
AccountSync app-config sections (see TriageApi.Api/Configuration/*.cs and
appsettings.json).

Reads directly from the live appsettings.json - both tools are pure/deterministic,
no LLM call needed (same philosophy as reprocess.py), so - like reprocess.py - they
just live in tools.dispatch_tool's fallthrough via toolset.py, no provider/api_key
context required.

Update never touches the file: it returns a Mongo script instead, the same
copy/download-rendered artifact the reprocess flow produces (see
providers.py's _capture_extras, which picks up any tool result carrying a
"script" key generically, not just from one named tool).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]  # .../NewProject
_ENV_OVERRIDE = "TRIAGE_API_APPSETTINGS_PATH"
_DEFAULT_APPSETTINGS_PATH = _REPO_ROOT / "src" / "TriageApi.Api" / "appsettings.json"

CONFIG_SECTIONS = ("LoanBoarding", "CustomerSync", "AccountSync")
_OPERATIONS = {"set": "$set", "add_to_list": "$addToSet", "remove_from_list": "$pull"}

# The appsettings.json section name and its Mongo collection name are different by
# design, not a "file name" convention - given explicitly, not derived.
_COLLECTION_NAMES = {
    "LoanBoarding": "LoanBoardingConfig",
    "CustomerSync": "CustomerAppConfig",
    "AccountSync": "AccountSyncSummaryConfig",
}


def _appsettings_path() -> Path:
    import os

    override = os.environ.get(_ENV_OVERRIDE)
    return Path(override) if override else _DEFAULT_APPSETTINGS_PATH


def _load_appsettings() -> dict:
    # Deliberately not cached (unlike data_sources.py's fixtures) - this file is
    # small, read infrequently, and a stale read here would show a user a config
    # value that's already wrong.
    with open(_appsettings_path(), encoding="utf-8") as f:
        return json.load(f)


def get_app_config_value(config: str, key: str | None = None) -> dict[str, Any]:
    if config not in CONFIG_SECTIONS:
        return {"found": False, "message": f"'{config}' isn't a known config section. Valid sections: {', '.join(CONFIG_SECTIONS)}."}

    section = _load_appsettings().get(config)
    if section is None:
        return {"found": False, "message": f"No '{config}' section found in the current app config."}

    if key is None:
        return {"found": True, "config": config, "value": section}

    if key not in section:
        return {"found": False, "message": f"'{config}' has no key named '{key}'."}

    return {"found": True, "config": config, "key": key, "value": section[key]}


def _infer_mongo_literal(value: str) -> str:
    """Fallback for when there's no existing value/list-item to match a type
    against (e.g. the current value is null): a bare number/boolean/null, or a
    properly quoted-and-escaped string otherwise."""
    lowered = value.strip().lower()
    if lowered in ("true", "false"):
        return lowered
    if lowered == "null":
        return "null"
    try:
        int(value)
        return value
    except ValueError:
        pass
    try:
        float(value)
        return value
    except ValueError:
        pass
    return json.dumps(value)


def _coerce_to_matching_type(value: str, reference: Any) -> str:
    """Renders `value` (always a plain string - see the tool schema) as the
    Mongo/JS literal matching `reference`'s type - critical because config
    fields that read as numeric strings (dealer codes like "93159") are
    actually *strings* in the data; blindly guessing from the string's own
    shape would render them as bare numbers and corrupt the array's type
    consistency (a later $pull with the "same" value wouldn't match)."""
    if reference is None:
        return _infer_mongo_literal(value)
    if isinstance(reference, bool):
        return "true" if value.strip().lower() in ("true", "1", "yes") else "false"
    if isinstance(reference, (int, float)):
        try:
            return str(int(value))
        except ValueError:
            try:
                return str(float(value))
            except ValueError:
                pass  # fall through to string
    return json.dumps(value)


def generate_config_update_script(config: str, key: str, operation: str, value: str) -> dict[str, Any]:
    if config not in CONFIG_SECTIONS:
        return {"error": f"'{config}' isn't a known config section. Valid sections: {', '.join(CONFIG_SECTIONS)}."}

    section = _load_appsettings().get(config)
    if section is None:
        return {"error": f"No '{config}' section found in the current app config."}

    if key not in section:
        return {"error": f"'{config}' has no key named '{key}'."}

    mongo_op = _OPERATIONS.get(operation)
    if mongo_op is None:
        return {"error": f"Unknown operation '{operation}'. Use one of: {', '.join(_OPERATIONS)}."}

    current = section[key]
    if operation in ("add_to_list", "remove_from_list") and not isinstance(current, list):
        return {"error": f"'{key}' in '{config}' isn't a list - use operation 'set' instead."}
    if operation == "set" and isinstance(current, list):
        return {"error": f"'{key}' in '{config}' is a list - use 'add_to_list' or 'remove_from_list' instead of 'set'."}

    if operation == "set":
        reference = current
    else:
        reference = current[0] if current else None  # match the existing list items' type
    literal = _coerce_to_matching_type(value, reference)
    collection = _COLLECTION_NAMES[config]
    script = f"""// CONFIG UPDATE SCRIPT: Run in Mongo Shell / Compass
db.{collection}.updateOne(
  {{ "_id": "{config}" }},
  {{ {mongo_op}: {{ "{key}": {literal} }} }}
);"""
    return {"script": script}


_KEY_REFERENCE = (
    "LoanBoarding - CreateLoanOnIdenticalAppId, Dealers, EnableAfsFlow, EnableAlfaFlow, "
    "EnableDay1Throttling, EnablePrePilotMode, EnableRetryFromLoanBoardingRecords, "
    "ExcludedCities, FicoScoreThreshold, MaxConcurrencyForRetry, MaxRetries, "
    "MinConcurrencyForRetry, MockResponses, MongoRecordDeleteDelaySeconds, "
    "RemoveLoanBoardingRecordsOnSuccess, ResetRetryCounterAfterPublish, RetryIntervalMinutes, "
    "SaveLoanBoardingRecords, States. "
    "CustomerSync - CustomerEventsRetentionInDays, DarkModeEnabled, "
    "FailedHoganNotificationsRetentionInDays, GenerateCustomeEvent, MockGUID, MockMQCalls, "
    "MockMongoDB, NotificationAuditRetentionInDays, CustomerEventsRetryAfterInMinutes, "
    "MaxRetryCount. "
    "AccountSync - TTLInMinutes, AlfaSystemDate."
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_app_config_value",
        "description": (
            "Reads the current value of an app-config key (or a whole section) from the "
            "live appsettings.json. Known sections and their keys: " + _KEY_REFERENCE + " "
            "Omit key to get the entire section as one object. If the result is an object "
            "with found:false, that section/key doesn't exist - relay the message plainly, "
            "don't guess a value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config": {"type": "string", "enum": list(CONFIG_SECTIONS), "description": "Which config section to read."},
                "key": {
                    "type": "string",
                    "description": "Optional specific key within that section (e.g. Dealers, MaxRetries). Omit for the whole section.",
                },
            },
            "required": ["config"],
        },
    },
    {
        "name": "generate_config_update_script",
        "description": (
            "Builds the Mongo script to change one app-config key - never edits the file "
            "directly. Known sections and their keys: " + _KEY_REFERENCE + " "
            "operation is 'set' for a scalar/boolean value, 'add_to_list' or "
            "'remove_from_list' for a single item in a list-typed key (e.g. Dealers, "
            "States, ExcludedCities) - check get_app_config_value first if you're not sure "
            "whether a key is a list. value is always a plain string (e.g. \"true\", \"5\", "
            "\"93159\") - it's rendered as the correctly-typed Mongo literal automatically. "
            "Don't repeat the returned script text in your reply - it's rendered separately "
            "with copy/download options; just confirm briefly what it changes. If the result "
            "is an object with an error field, relay it plainly and don't call the tool again "
            "with guessed values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "config": {"type": "string", "enum": list(CONFIG_SECTIONS), "description": "Which config section to update."},
                "key": {"type": "string", "description": "The key being changed, e.g. Dealers, MaxRetries."},
                "operation": {
                    "type": "string",
                    "enum": list(_OPERATIONS),
                    "description": "'set' to replace a scalar/boolean value; 'add_to_list'/'remove_from_list' to add or remove one item from a list-typed key.",
                },
                "value": {
                    "type": "string",
                    "description": "The new value (for 'set'), or the single item to add/remove (for list operations), as a plain string.",
                },
            },
            "required": ["config", "key", "operation", "value"],
        },
    },
]


def dispatch_tool(name: str, tool_input: dict[str, Any]) -> Any:
    if name == "get_app_config_value":
        return get_app_config_value(config=tool_input["config"], key=tool_input.get("key"))
    if name == "generate_config_update_script":
        return generate_config_update_script(
            config=tool_input["config"],
            key=tool_input["key"],
            operation=tool_input["operation"],
            value=tool_input["value"],
        )
    raise ValueError(f"Unknown tool: {name}")

"""Locating and resolving the transaction/issue date from free text.

Three-way outcome, per the agreed spec:
  - already YYYYMMDD                -> use directly, no confirmation needed
  - parseable but a different format -> normalize, but a human must confirm before
                                         it's written into the final schema
  - not provided, or not parseable   -> "missing" (UI prompts) or
                                         "invalid_needs_reprompt" (ask again) -
                                         never silently guess a date
"""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateutil_parser
from dateutil.parser import ParserError

from query_intake.models import DateResolution

_YYYYMMDD = re.compile(r"\b\d{8}\b")
_ISO_LIKE = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
_SLASH_DATE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b")
_MONTH_NAMES = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_MONTH_DAY_YEAR = re.compile(
    rf"\b(?:{_MONTH_NAMES})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}}\b", re.IGNORECASE
)
_DAY_MONTH_YEAR = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTH_NAMES})\.?,?\s+\d{{2,4}}\b", re.IGNORECASE
)

_CANDIDATE_PATTERNS = (_YYYYMMDD, _ISO_LIKE, _SLASH_DATE, _MONTH_DAY_YEAR, _DAY_MONTH_YEAR)


def find_date_span(text: str) -> str | None:
    """Best-effort isolation of a date-like substring. Returns None if nothing looks like a date."""
    for pattern in _CANDIDATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def resolve_date(raw_date_text: str | None) -> DateResolution:
    if raw_date_text is None:
        return DateResolution(raw_input=None, normalized=None, status="missing")

    stripped = raw_date_text.strip()

    if _YYYYMMDD.fullmatch(stripped):
        if _is_plausible_yyyymmdd(stripped):
            return DateResolution(raw_input=raw_date_text, normalized=stripped, status="valid_no_confirm_needed")
        return DateResolution(
            raw_input=raw_date_text,
            normalized=None,
            status="invalid_needs_reprompt",
            message=f"'{raw_date_text}' isn't a valid date - please provide it as YYYYMMDD.",
        )

    try:
        parsed = dateutil_parser.parse(stripped)
    except (ParserError, ValueError, OverflowError):
        return DateResolution(
            raw_input=raw_date_text,
            normalized=None,
            status="invalid_needs_reprompt",
            message=f"Could not understand '{raw_date_text}' as a date - please provide it as YYYYMMDD.",
        )

    normalized = parsed.strftime("%Y%m%d")
    # %-d (no leading zero) is a glibc/macOS strftime extension, not portable to
    # Windows' C runtime - build the "day" part manually instead of relying on it.
    human_readable = f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    return DateResolution(
        raw_input=raw_date_text,
        normalized=normalized,
        status="needs_confirmation",
        message=f"Interpreted '{raw_date_text}' as {human_readable} ({normalized}) - confirm?",
    )


def _is_plausible_yyyymmdd(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True

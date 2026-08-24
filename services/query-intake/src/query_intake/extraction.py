"""Deterministic, regex-based identifier extraction.

Identifiers are pulled out with pattern matching, not asked of an LLM - an LLM is
markedly less reliable at faithfully reproducing an exact long string than at
classification, and a wrong transcription here (a GUID, an account number) is a
silent correctness bug downstream. When a label isn't found next to a number, this
returns None rather than guessing which of several numbers in the text is which.

ECN/AccountNumber patterns are a best-effort default (ECN's length matches the one
confirmed real example we have - custNbr in the OXCU054 sample, 15 digits - but
these haven't been validated against a representative sample of real queries).
Tighten these once real query examples are available.
"""

from __future__ import annotations

import re

from query_intake.date_parsing import find_date_span
from query_intake.models import ExtractedIdentifiers

_GUID_PATTERN = re.compile(
    r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"
)

_ECN_PATTERN = re.compile(
    r"\b(?:ECN|enterprise\s+customer\s+number)\b[\s:#-]*([0-9]{6,20})",
    re.IGNORECASE,
)

# The label alternatives must be grouped together (not left as a bare top-level `|`)
# so the separator + capture apply to both "account ..." and "acct ..." forms - a
# top-level alternation here would let a bare "account" match with no number at all.
# The lookahead requires at least one digit in the captured token, so a plain word
# like "settings" right after "account" (e.g. "account settings need review") can't
# be mistaken for an account number.
_ACCOUNT_PATTERN = re.compile(
    r"\b(?:(?:loan\s+)?account(?:\s*(?:number|no\.?|#))?|acct\.?\s*(?:number|#)?)"
    r"[\s:#-]*(?=[0-9A-Za-z-]*\d)([0-9A-Za-z-]{4,20})\b",
    re.IGNORECASE,
)


def extract_identifiers(query_text: str) -> ExtractedIdentifiers:
    correlation_id = _first_match(_GUID_PATTERN, query_text)
    ecn = _first_match(_ECN_PATTERN, query_text)
    account_number = _first_match(_ACCOUNT_PATTERN, query_text)
    raw_date_text = find_date_span(query_text)

    return ExtractedIdentifiers(
        correlation_id=correlation_id,
        ecn=ecn,
        account_number=account_number,
        raw_date_text=raw_date_text,
    )


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    # GUID pattern has no capture group (the whole match is the id); labeled
    # patterns capture just the number/value after the label.
    return match.group(1) if match.groups() else match.group(0)

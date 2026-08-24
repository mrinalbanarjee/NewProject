"""
Turns the raw, code-laden strings from Hogan/the failure feed into plain
English, so tool output never puts an operational code (OXCU200E, 0XCA015E,
correlationId-shaped GUIDs, ...) in front of a non-technical reader. Nothing
here is guessed - every mapping and pattern was reverse-engineered from the
actual sample payloads (see the field-by-(request type, embedded code) tally
that produced `REQUEST_MESSAGE_TYPE_LABELS` and `_FIELD_LABELS`).
"""

from __future__ import annotations

import re

REQUEST_MESSAGE_TYPE_LABELS: dict[str, str] = {
    # Confirmed by cross-tabulating every (requestMessageType, embedded error
    # code) pair in FailureListResponse: OXCU305 only ever carries phone/consent
    # errors (OXCU100E/105E/110E/115E/120E), OXCU318 only ever carries
    # name/address/date-of-birth errors (OXCU200E/205E/210E/215E/220E/225E).
    "OXCU305": "Customer Phone & Consent Update",
    "OXCU318": "Customer Delta Update (Name / Address / Date of Birth)",
}


def describe_request_message_type(code: str) -> str:
    return REQUEST_MESSAGE_TYPE_LABELS.get(code, f"Customer update ({code})")


_FIELD_LABELS = {
    "NAME": "Name",
    "ADDRESS": "Address",
    "PHONE": "Phone",
    "CONSENT": "Consent",
    "DOB": "Date of birth",
}
_CATEGORY_RE = re.compile(r"ERROR IN APPLYING (\w+) MAINTENANCE FOR CUSTOMER", re.IGNORECASE)
_LEADING_NUMERIC_CODE_RE = re.compile(r"^\d+\s+")


def humanize_response_text(response_text: str) -> str:
    """
    Raw shape: "<CODE>,ERROR IN APPLYING <FIELD> MAINTENANCE FOR CUSTOMER,<NUM>  <DETAIL>, <NUM>  <DETAIL> RC:<CODE>"
    e.g. "OXCU220E,ERROR IN APPLYING NAME MAINTENANCE FOR CUSTOMER,07430  NAME FIELD EXCEEDS MAX LENGTH, 07430  NAME FIELD EXCEEDS MAX LENGTH RC:OXCU220E"
    -> "Name update failed - name field exceeds max length."
    """
    parts = [p.strip() for p in response_text.split(",")]

    field = "Customer record"
    if len(parts) > 1:
        match = _CATEGORY_RE.search(parts[1])
        if match:
            field = _FIELD_LABELS.get(match.group(1).upper(), match.group(1).title())

    detail = ""
    if len(parts) > 2:
        detail = _LEADING_NUMERIC_CODE_RE.sub("", parts[2]).strip()

    if not detail:
        return f"{field} update failed."
    return f"{field} update failed - {detail[0].upper()}{detail[1:].lower()}."


_TERM_FIXES = {
    "HOGAN": "Hogan",
    "ALFA": "Alfa",
    "ECN": "ECN",
    "CUAC": "CUAC",
    "ACCT": "account",
    "REQ": "request",
    "DUP": "duplicate",
    "PRES": "present",
    "REL": "relationship",
    "CUST": "customer",
}
_WORD_RE = re.compile(r"[A-Za-z]+")
_LEADING_STATUS_CODE_RE = re.compile(r"^\s*(\d{3})\s")


def _humanize_phrase(phrase: str) -> str:
    phrase = re.sub(r"\bREL\.\s*", "REL ", phrase, flags=re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        return _TERM_FIXES.get(word.upper(), word.lower())

    text = _WORD_RE.sub(repl, phrase).strip()
    return text[0].upper() + text[1:] if text else text


def humanize_boarding_text(loan_boarding_text: str) -> tuple[str, bool]:
    """
    Raw shape is a run of fixed-width, multi-space-separated fields mixing a
    leading HTTP-style status code, masked hex, a correlation GUID, a Hogan
    return code, and two human-readable ALL-CAPS phrases - only those two
    phrases are worth showing a non-technical reader.

    Returns (human-readable summary, whether the leading status code was 200 -
    i.e. whether the boarding step itself succeeded).
    """
    status_match = _LEADING_STATUS_CODE_RE.match(loan_boarding_text)
    succeeded = status_match is not None and status_match.group(1) == "200"

    tokens = re.split(r"\s{2,}", loan_boarding_text.strip())
    code_token_re = re.compile(
        r"^(0X[A-Z0-9]+|\d+|\*+[0-9a-f]*|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
        re.IGNORECASE,
    )
    phrases = [t for t in tokens if t and not code_token_re.match(t)]

    if not phrases:
        return "No further detail provided.", succeeded
    return ". ".join(_humanize_phrase(p) for p in phrases) + ".", succeeded

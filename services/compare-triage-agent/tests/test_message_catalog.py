from __future__ import annotations

from compare_triage_agent.message_catalog import (
    describe_request_message_type,
    humanize_boarding_text,
    humanize_response_text,
)


def test_describe_known_request_message_types():
    assert describe_request_message_type("OXCU305") == "Customer Phone & Consent Update"
    assert describe_request_message_type("OXCU318") == "Customer Delta Update (Name / Address / Date of Birth)"


def test_describe_unknown_request_message_type_falls_back_gracefully():
    assert describe_request_message_type("OXCU999") == "Customer update (OXCU999)"


def test_humanize_response_text_strips_codes_and_reads_naturally():
    raw = (
        "OXCU220E,ERROR IN APPLYING NAME MAINTENANCE FOR CUSTOMER,"
        "07430  NAME FIELD EXCEEDS MAX LENGTH, 07430  NAME FIELD EXCEEDS MAX LENGTH RC:OXCU220E"
    )
    result = humanize_response_text(raw)

    assert result == "Name update failed - Name field exceeds max length."
    assert "OXCU" not in result
    assert "RC:" not in result


def test_humanize_response_text_phone_and_consent_examples():
    assert humanize_response_text(
        "OXCU100E,ERROR IN APPLYING PHONE MAINTENANCE FOR CUSTOMER,"
        "09373  INVALID PHONE NUMBER ENTERED, 09373  INVALID PHONE NUMBER ENTERED RC:OXCU100E"
    ) == "Phone update failed - Invalid phone number entered."

    assert humanize_response_text(
        "OXCU115E,ERROR IN APPLYING CONSENT MAINTENANCE FOR CUSTOMER,"
        "08825  CONSENT DATE OUT OF RANGE, 08825  CONSENT DATE OUT OF RANGE RC:OXCU115E"
    ) == "Consent update failed - Consent date out of range."


def test_humanize_boarding_text_not_found_case():
    raw = (
        "404   ******f60d   ******19e3   a1c4357a-c7b8-4d5c-8a66-9f5ef28f2c31   "
        "0XCA015E   ACCOUNT NUMBER NOT FOUND ON HOGAN   70021  ACCT NOT PRES ON FILE"
    )
    summary, succeeded = humanize_boarding_text(raw)

    assert succeeded is False
    assert summary == "Account number not found on Hogan. Account not present on file."
    assert "0XCA015E" not in summary
    assert "a1c4357a" not in summary


def test_humanize_boarding_text_success_case():
    raw = (
        "200   ******78c7   ******e532   5bf5e3e9-67d8-446d-b891-c586e1415d09   "
        "0XCA000E   ACCOUNT SUCCESSFULLY BOARDED TO CUSTOMER   00000  NO ERRORS FOUND"
    )
    summary, succeeded = humanize_boarding_text(raw)

    assert succeeded is True
    assert summary == "Account successfully boarded to customer. No errors found."


def test_humanize_boarding_text_cuac_relationship_code_case():
    raw = (
        "403   ******763f   ******7191   4b158c55-f14a-4850-9799-a9365c71ffe5   "
        "0XCA020E   CUAC ALREADY EXISTS BETWEEN THE CUSTOMER AND ACCOUNT, BUT THE REL. CODE IS DIFFERENT   "
        "64189  ACCT REL ALREADY PRES ON CUST"
    )
    summary, succeeded = humanize_boarding_text(raw)

    assert succeeded is False
    assert summary == (
        "CUAC already exists between the customer and account, but the relationship code is different. "
        "Account relationship already present on customer."
    )

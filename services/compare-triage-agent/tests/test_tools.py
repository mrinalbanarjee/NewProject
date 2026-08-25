from __future__ import annotations

from compare_triage_agent.tools import dispatch_tool, get_account_compare_root_cause, list_customer_compare_mismatches


def test_list_mismatches_scoped_to_one_ecn_returns_only_mismatched_attributes():
    results = list_customer_compare_mismatches(ecn="6022768040250")

    assert len(results) == 1
    customer = results[0]
    assert customer.third_party_number == "1652580863"
    key_names = {m.key_name for m in customer.mismatches}
    assert key_names == {"BIRTHDATE_COMPARE", "ADDRESS_COMPARE"}
    assert all(m.comment for m in customer.mismatches)


def test_list_mismatches_omits_customers_with_no_mismatches():
    # ecn 4322585512452's first account matches; only its second account mismatches -
    # the customer should still be included, but with exactly the one mismatch.
    results = list_customer_compare_mismatches(ecn="4322585512452")

    assert len(results) == 1
    assert len(results[0].mismatches) == 1
    assert results[0].mismatches[0].key_name == "ACCOUNT_COMPARE"


def test_list_mismatches_without_ecn_covers_multiple_customers():
    results = list_customer_compare_mismatches()

    ecns = {c.ecn for c in results}
    assert "6022768040250" in ecns
    assert "5021410435426" in ecns  # has a NATIONALITYCODE_COMPARE and PREFERREDLANGUAGE_COMPARE mismatch only


def test_account_root_cause_returns_one_entry_per_mismatched_account():
    results = get_account_compare_root_cause(ecn="0444769043821")

    assert {r.account_number for r in results} == {"0580084955", "9906505513"}


def test_account_root_cause_includes_primary_boarding_status():
    results = get_account_compare_root_cause(ecn="0444769043821", account_number="0580084955")

    assert len(results) == 1
    primary = results[0].primary_boarding_status
    assert primary is not None
    assert primary.succeeded is False
    assert "Duplicate" in primary.summary
    assert "OXCA" not in primary.summary.upper().replace(" ", "")
    assert primary.event_time == "2026-08-04T15:03:13.294Z"
    assert primary.correlation_id == "44792fe1-4f9d-4693-b0e8-0e02f144d09e"


def test_account_root_cause_boarding_summary_reflects_success():
    results = get_account_compare_root_cause(ecn="0444769043821", account_number="9906505513")

    primary = results[0].primary_boarding_status
    assert primary is not None
    assert primary.succeeded is True
    assert "successfully boarded" in primary.summary.lower()


def test_dependent_failure_descriptions_have_no_embedded_codes():
    results = get_account_compare_root_cause(ecn="0444769043821", account_number="0580084955")

    dependent = results[0].dependent_failures
    assert len(dependent) == 2
    for failure in dependent:
        assert "OXCU" not in failure.description
        assert "RC:" not in failure.description
        assert failure.update_type == "Customer Phone & Consent Update" or failure.update_type == (
            "Customer Delta Update (Name / Address / Date of Birth)"
        )
    # first dependent failure is the phone-maintenance one (OXCU305 / OXCU100E)
    assert dependent[0].update_type == "Customer Phone & Consent Update"
    assert "invalid phone number" in dependent[0].description.lower()
    # second is the name-maintenance one (OXCU318 / OXCU200E)
    assert dependent[1].update_type == "Customer Delta Update (Name / Address / Date of Birth)"
    assert "invalid character in name field" in dependent[1].description.lower()


def test_account_root_cause_only_includes_failures_after_boarding_event_time():
    results = get_account_compare_root_cause(ecn="0444769043821", account_number="0580084955")

    dependent = results[0].dependent_failures
    # Both known failures for this account (08-19 and 08-23) fall after the
    # 08-04 boarding event time, so both should surface, in chronological order.
    assert [d.event_time_stamp for d in dependent] == [
        "2026-08-19T01:21:20.295+00:00",
        "2026-08-23T17:58:12.297+00:00",
    ]


def test_account_root_cause_unknown_ecn_returns_empty():
    assert get_account_compare_root_cause(ecn="0000000000000") == []


def test_account_root_cause_ignores_non_account_compare_mismatches():
    # ecn 5374884941847 has a NAME_COMPARE mismatch and one mismatched account
    # (7894756224) - only the account mismatch should drive a result.
    results = get_account_compare_root_cause(ecn="5374884941847")

    assert len(results) == 1
    assert results[0].account_number == "7894756224"


# -- dispatch_tool: found/not-found signalling at the LLM-facing boundary --


def test_dispatch_list_mismatches_unknown_ecn_reports_not_found():
    result = dispatch_tool("list_customer_compare_mismatches", {"ecn": "0000000000000"})

    assert result == {"found": False, "message": "No compare record found for ECN '0000000000000'."}


def test_dispatch_list_mismatches_known_ecn_with_zero_mismatches_is_distinct_from_not_found():
    # ecn 5756865116697 exists and every attribute matched - this must NOT look
    # like the unknown-ECN case above, even though both start from an "empty" result.
    result = dispatch_tool("list_customer_compare_mismatches", {"ecn": "5756865116697"})

    assert result["found"] is True
    assert result["mismatches"] == []
    assert "5756865116697" in result["message"]


def test_dispatch_list_mismatches_known_ecn_with_mismatches_returns_plain_list():
    result = dispatch_tool("list_customer_compare_mismatches", {"ecn": "6022768040250"})

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["ecn"] == "6022768040250"


def test_dispatch_root_cause_unknown_ecn_reports_not_found():
    result = dispatch_tool("get_account_compare_root_cause", {"ecn": "0000000000000"})

    assert result == {"found": False, "message": "No compare record found for ECN '0000000000000'."}


def test_dispatch_root_cause_known_ecn_but_unmatched_account_reports_not_found():
    # ecn 0444769043821 exists and has ACCOUNT_COMPARE mismatches, but not for this account number.
    result = dispatch_tool(
        "get_account_compare_root_cause", {"ecn": "0444769043821", "account_number": "9999999999"}
    )

    assert result == {
        "found": False,
        "message": "No ACCOUNT_COMPARE mismatch found for ECN '0444769043821' and account '9999999999'.",
    }


def test_dispatch_root_cause_known_ecn_with_no_account_compare_mismatches_reports_not_found():
    # ecn 5756865116697 exists but has no mismatches of any kind, let alone ACCOUNT_COMPARE.
    result = dispatch_tool("get_account_compare_root_cause", {"ecn": "5756865116697"})

    assert result == {
        "found": False,
        "message": "No ACCOUNT_COMPARE mismatches found for ECN '5756865116697'.",
    }


def test_dispatch_root_cause_known_ecn_with_match_returns_plain_list():
    result = dispatch_tool("get_account_compare_root_cause", {"ecn": "0444769043821"})

    assert isinstance(result, list)
    assert {r["account_number"] for r in result} == {"0580084955", "9906505513"}

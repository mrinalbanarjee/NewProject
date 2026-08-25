from __future__ import annotations

from compare_triage_agent import classifier, toolset


def test_tool_definitions_include_the_classify_and_script_tools():
    names = {t["name"] for t in toolset.TOOL_DEFINITIONS}
    assert names == {
        "list_customer_compare_mismatches",
        "get_account_compare_root_cause",
        "classify_account_compare_failures",
        "generate_reprocess_script",
        "get_app_config_value",
        "generate_config_update_script",
    }


def test_dispatch_tool_delegates_plain_data_tools_to_tools_module():
    # list_customer_compare_mismatches doesn't need provider/api_key - just proves
    # the fallthrough to tools.dispatch_tool still works through the combined registry.
    result = toolset.dispatch_tool(
        "list_customer_compare_mismatches", {"ecn": "6022768040250"}, provider="google", api_key="unused"
    )
    assert isinstance(result, list)
    assert result[0]["ecn"] == "6022768040250"


def test_dispatch_classify_unknown_ecn_reports_not_found():
    result = toolset.dispatch_tool(
        "classify_account_compare_failures", {"ecn": "0000000000000"}, provider="google", api_key="fake-key"
    )
    assert result == {"found": False, "message": "No compare record found for ECN '0000000000000'."}


def test_dispatch_classify_known_ecn_returns_accounts(monkeypatch):
    monkeypatch.setitem(classifier._CLASSIFIERS, "google", lambda *a: {"diagnostics": []})

    result = toolset.dispatch_tool(
        "classify_account_compare_failures", {"ecn": "0444769043821"}, provider="google", api_key="fake-key"
    )

    assert result["found"] is True
    assert {a["accountNumber"] for a in result["accounts"]} == {"0580084955", "9906505513"}
    # camelCase, matching the fixed diagnostics contract, not snake_case field names
    assert "primaryCorrelationId" in result["accounts"][0]
    assert "primary_correlation_id" not in result["accounts"][0]


def test_dispatch_classify_scoped_to_unmatched_account_reports_not_found():
    result = toolset.dispatch_tool(
        "classify_account_compare_failures",
        {"ecn": "0444769043821", "account_number": "9999999999"},
        provider="google",
        api_key="fake-key",
    )
    assert result == {
        "found": False,
        "message": "No ACCOUNT_COMPARE mismatch found for ECN '0444769043821' and account '9999999999'.",
    }


def test_dispatch_generate_reprocess_script_builds_script():
    result = toolset.dispatch_tool(
        "generate_reprocess_script",
        {"primary_correlation_id": "CORR-PRIMARY", "selected_correlation_ids": ["CORR-DEP-1"]},
        provider="google",
        api_key="unused",
    )
    assert "db.customerevent.updateMany" in result["script"]
    assert "CORR-PRIMARY" in result["script"]
    assert "CORR-DEP-1" in result["script"]


def test_dispatch_generate_reprocess_script_with_nothing_selected_returns_error_not_raise():
    result = toolset.dispatch_tool(
        "generate_reprocess_script",
        {"selected_correlation_ids": []},
        provider="google",
        api_key="unused",
    )
    assert "error" in result


def test_dispatch_get_app_config_value_routes_through_to_config_tools():
    result = toolset.dispatch_tool(
        "get_app_config_value", {"config": "LoanBoarding", "key": "Dealers"}, provider="google", api_key="unused"
    )
    assert result["found"] is True
    assert "93159" in result["value"]


def test_dispatch_generate_config_update_script_routes_through_to_config_tools():
    result = toolset.dispatch_tool(
        "generate_config_update_script",
        {"config": "CustomerSync", "key": "MaxRetryCount", "operation": "set", "value": "5"},
        provider="google",
        api_key="unused",
    )
    assert "db.CustomerAppConfig.updateOne" in result["script"]
    assert '"MaxRetryCount": 5' in result["script"]

from __future__ import annotations

import json

import pytest

from compare_triage_agent import config_tools

_SAMPLE_APPSETTINGS = {
    "LoanBoarding": {
        "Dealers": ["29002", "93159"],
        "MaxRetries": 3,
        "MockResponses": False,
        "ExcludedCities": None,
    },
    "CustomerSync": {
        "MaxRetryCount": 3,
        "DarkModeEnabled": False,
    },
}


@pytest.fixture
def isolated_appsettings(tmp_path, monkeypatch):
    path = tmp_path / "appsettings.json"
    path.write_text(json.dumps(_SAMPLE_APPSETTINGS), encoding="utf-8")
    monkeypatch.setenv(config_tools._ENV_OVERRIDE, str(path))
    return path


def test_get_app_config_value_whole_section(isolated_appsettings):
    result = config_tools.get_app_config_value("LoanBoarding")
    assert result["found"] is True
    assert result["value"]["Dealers"] == ["29002", "93159"]


def test_get_app_config_value_single_key(isolated_appsettings):
    result = config_tools.get_app_config_value("LoanBoarding", "Dealers")
    assert result == {"found": True, "config": "LoanBoarding", "key": "Dealers", "value": ["29002", "93159"]}


def test_get_app_config_value_unknown_section():
    result = config_tools.get_app_config_value("NotASection")
    assert result["found"] is False
    assert "NotASection" in result["message"]


def test_get_app_config_value_unknown_key(isolated_appsettings):
    result = config_tools.get_app_config_value("LoanBoarding", "NotAKey")
    assert result["found"] is False
    assert "NotAKey" in result["message"]


def test_generate_config_update_script_set_matches_int_type(isolated_appsettings):
    result = config_tools.generate_config_update_script("CustomerSync", "MaxRetryCount", "set", "7")
    assert '$set: { "MaxRetryCount": 7 }' in result["script"]  # unquoted - matches existing int type
    assert "db.CustomerAppConfig.updateOne" in result["script"]  # collection name != section name


def test_generate_config_update_script_set_matches_bool_type(isolated_appsettings):
    result = config_tools.generate_config_update_script("CustomerSync", "DarkModeEnabled", "set", "true")
    assert '$set: { "DarkModeEnabled": true }' in result["script"]


def test_generate_config_update_script_add_to_list_keeps_string_type(isolated_appsettings):
    # Dealer codes look numeric but are strings in the data - must stay quoted,
    # otherwise a later $pull with the "same" value wouldn't match (type mismatch).
    result = config_tools.generate_config_update_script("LoanBoarding", "Dealers", "add_to_list", "12345")
    assert '$addToSet: { "Dealers": "12345" }' in result["script"]
    assert "db.LoanBoardingConfig.updateOne" in result["script"]


@pytest.mark.parametrize(
    "config,expected_collection",
    [
        ("LoanBoarding", "LoanBoardingConfig"),
        ("CustomerSync", "CustomerAppConfig"),
        ("AccountSync", "AccountSyncSummaryConfig"),
    ],
)
def test_generate_config_update_script_uses_the_right_collection_per_section(config, expected_collection, tmp_path, monkeypatch):
    path = tmp_path / "appsettings.json"
    path.write_text(json.dumps({config: {"SomeKey": 1}}), encoding="utf-8")
    monkeypatch.setenv(config_tools._ENV_OVERRIDE, str(path))

    result = config_tools.generate_config_update_script(config, "SomeKey", "set", "2")

    assert f"db.{expected_collection}.updateOne" in result["script"]


def test_generate_config_update_script_remove_from_list_keeps_string_type(isolated_appsettings):
    result = config_tools.generate_config_update_script("LoanBoarding", "Dealers", "remove_from_list", "93159")
    assert '$pull: { "Dealers": "93159" }' in result["script"]


def test_generate_config_update_script_set_on_list_key_is_rejected(isolated_appsettings):
    result = config_tools.generate_config_update_script("LoanBoarding", "Dealers", "set", "12345")
    assert "error" in result
    assert "list" in result["error"].lower()


def test_generate_config_update_script_add_to_list_on_scalar_key_is_rejected(isolated_appsettings):
    result = config_tools.generate_config_update_script("LoanBoarding", "MaxRetries", "add_to_list", "1")
    assert "error" in result
    assert "list" in result["error"].lower()


def test_generate_config_update_script_unknown_key_is_rejected(isolated_appsettings):
    result = config_tools.generate_config_update_script("LoanBoarding", "NotAKey", "set", "1")
    assert "error" in result
    assert "NotAKey" in result["error"]


def test_generate_config_update_script_unknown_operation_is_rejected(isolated_appsettings):
    result = config_tools.generate_config_update_script("LoanBoarding", "MaxRetries", "delete_everything", "1")
    assert "error" in result


def test_generate_config_update_script_falls_back_to_heuristic_when_current_value_is_null(isolated_appsettings):
    # ExcludedCities is null - there's no existing value/list-item to match a type
    # against, so this exercises the _infer_mongo_literal fallback path.
    result = config_tools.generate_config_update_script("LoanBoarding", "ExcludedCities", "set", "Chicago")
    assert '$set: { "ExcludedCities": "Chicago" }' in result["script"]


def test_dispatch_tool_routes_both_config_tools(isolated_appsettings):
    get_result = config_tools.dispatch_tool("get_app_config_value", {"config": "LoanBoarding", "key": "Dealers"})
    assert get_result["found"] is True

    script_result = config_tools.dispatch_tool(
        "generate_config_update_script",
        {"config": "CustomerSync", "key": "MaxRetryCount", "operation": "set", "value": "9"},
    )
    assert "script" in script_result


def test_dispatch_tool_rejects_unknown_tool_name():
    with pytest.raises(ValueError):
        config_tools.dispatch_tool("not_a_real_tool", {})


def test_reads_the_real_appsettings_json_by_default():
    # No isolated_appsettings fixture here - exercises the actual default path
    # against the live TriageApi.Api/appsettings.json this whole feature was built for.
    result = config_tools.get_app_config_value("LoanBoarding", "Dealers")
    assert result["found"] is True
    assert isinstance(result["value"], list)
    assert len(result["value"]) > 0

from __future__ import annotations

from compare_triage_agent import classifier
from compare_triage_agent.models import AccountRootCause, BoardingStatus, DependentFailure


def _account(dependent_failures: list[DependentFailure], succeeded: bool = False) -> AccountRootCause:
    return AccountRootCause(
        ecn="1234567890123",
        account_number="9999999999",
        compare_comment="AccountNumber - Hogan: '9999999999', Alfa: '0000000000'",
        is_cuac_code_matched=False,
        primary_boarding_status=BoardingStatus(
            account_number="9999999999",
            correlation_id="CORR-PRIMARY-1",
            succeeded=succeeded,
            summary="Duplicate boarding request received for same account and ECN. Duplicate request rejected.",
            event_time="2026-08-04T15:03:13.294Z",
        ),
        dependent_failures=dependent_failures,
    )


def _dependent_failure(correlation_id: str = "CORR-DEP-1") -> DependentFailure:
    return DependentFailure(
        correlation_id=correlation_id,
        update_type="Customer Phone & Consent Update",
        raw_request_message_type="OXCU305",
        description="Phone update failed - Invalid phone number entered.",
        event_time_stamp="2026-08-19T01:21:20.295+00:00",
    )


def test_classify_account_skips_llm_call_when_no_dependent_failures(monkeypatch):
    calls = []
    monkeypatch.setitem(classifier._CLASSIFIERS, "google", lambda *a: calls.append(a) or {})

    result = classifier.classify_account("google", "key", _account([]))

    assert calls == []  # never invoked - nothing to classify
    assert result.diagnostics == []
    assert result.primary_correlation_id == "CORR-PRIMARY-1"
    assert result.primary_succeeded is False
    assert result.account_number == "9999999999"


def test_classify_account_parses_provider_response_into_diagnostics(monkeypatch):
    fake_response = {
        "diagnostics": [
            {
                "correlationId": "CORR-DEP-1",
                "requestMessageType": "OXCU305",
                "eventTimestamp": "2026-08-19T01:21:20.295+00:00",
                "failureReason": "Invalid phone number entered in the payload.",
                "canBeReprocessed": False,
                "recommendation": "Correct the phone number at the Alfa source system before reprocessing.",
            }
        ]
    }
    monkeypatch.setitem(classifier._CLASSIFIERS, "openai", lambda api_key, model, prompt: fake_response)

    result = classifier.classify_account("openai", "key", _account([_dependent_failure()]))

    assert len(result.diagnostics) == 1
    entry = result.diagnostics[0]
    assert entry.correlation_id == "CORR-DEP-1"
    assert entry.request_message_type == "OXCU305"
    assert entry.can_be_reprocessed is False
    assert "phone number" in entry.recommendation.lower()


def test_classify_account_passes_the_resolved_reasoning_tier_model(monkeypatch):
    captured = {}

    def fake_classifier(api_key, model, prompt):
        captured["model"] = model
        captured["prompt"] = prompt
        return {"diagnostics": []}

    monkeypatch.setitem(classifier._CLASSIFIERS, "anthropic", fake_classifier)

    classifier.classify_account("anthropic", "key", _account([_dependent_failure()]))

    assert captured["model"] == classifier.resolve_model("anthropic", "reasoning")
    assert "Collateral / Dependency Failure" in captured["prompt"]
    assert "Inherent Data Validation Failure" in captured["prompt"]
    assert "CORR-DEP-1" in captured["prompt"]


def test_classify_account_handles_missing_boarding_record(monkeypatch):
    monkeypatch.setitem(classifier._CLASSIFIERS, "google", lambda *a: {"diagnostics": []})

    account = AccountRootCause(
        ecn="1234567890123",
        account_number="9999999999",
        compare_comment="",
        is_cuac_code_matched=None,
        primary_boarding_status=None,
        dependent_failures=[_dependent_failure()],
    )
    result = classifier.classify_account("google", "key", account)

    assert result.primary_correlation_id is None
    assert result.primary_succeeded is None


def test_classify_ecn_classifies_every_mismatched_account(monkeypatch):
    # ecn 0444769043821 has two mismatched ACCOUNT_COMPARE accounts in the bundled fixtures.
    monkeypatch.setitem(classifier._CLASSIFIERS, "google", lambda *a: {"diagnostics": []})

    results = classifier.classify_ecn("google", "key", ecn="0444769043821")

    assert {r.account_number for r in results} == {"0580084955", "9906505513"}
    assert all(r.ecn == "0444769043821" for r in results)


def test_classify_account_retries_on_fast_tier_when_reasoning_model_not_found(monkeypatch):
    calls = []

    def fake_classifier(api_key, model, prompt):
        calls.append(model)
        if len(calls) == 1:
            raise Exception("model gemini-3.6-pro is not found")
        return {"diagnostics": []}

    monkeypatch.setitem(classifier._CLASSIFIERS, "google", fake_classifier)

    result = classifier.classify_account("google", "key", _account([_dependent_failure()]))

    assert len(calls) == 2
    assert calls[0] == classifier.resolve_model("google", "reasoning")
    assert calls[1] == classifier.resolve_model("google", "fast")
    assert result.diagnostics == []


def test_classify_account_does_not_swallow_unrelated_errors(monkeypatch):
    def fake_classifier(api_key, model, prompt):
        raise Exception("insufficient_quota: credit balance too low")

    monkeypatch.setitem(classifier._CLASSIFIERS, "google", fake_classifier)

    try:
        classifier.classify_account("google", "key", _account([_dependent_failure()]))
        assert False, "expected an exception"
    except Exception as exc:
        assert "insufficient_quota" in str(exc)


def test_diagnostics_json_schema_matches_the_required_field_contract():
    item_schema = classifier.DIAGNOSTICS_JSON_SCHEMA["properties"]["diagnostics"]["items"]
    assert set(item_schema["required"]) == {
        "correlationId",
        "requestMessageType",
        "eventTimestamp",
        "failureReason",
        "canBeReprocessed",
        "recommendation",
    }
    assert item_schema["properties"]["canBeReprocessed"]["type"] == "boolean"
    assert item_schema["additionalProperties"] is False

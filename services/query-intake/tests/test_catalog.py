import pytest

from query_intake.catalog import (
    CatalogValidationError,
    is_known_lob,
    is_known_service_area,
    validate_candidate,
)

VALID_ISSUE_CODE = "PhoneNumber_Not_Updated_In_Alfa_From_Hogan"


def test_known_lob():
    assert is_known_lob("LoanAdmin") is True
    assert is_known_lob("Payment") is False


def test_known_service_area():
    assert is_known_service_area("LoanAdmin", "HoganToAlfaSync") is True
    assert is_known_service_area("LoanAdmin", "SomethingElse") is False
    assert is_known_service_area("Payment", "HoganToAlfaSync") is False


def test_validate_candidate_passes_for_correct_triple():
    validate_candidate(VALID_ISSUE_CODE, "LoanAdmin", "HoganToAlfaSync")


def test_validate_candidate_rejects_unknown_issue_code():
    with pytest.raises(CatalogValidationError):
        validate_candidate("NotARealIssueCode", "LoanAdmin", "HoganToAlfaSync")


def test_validate_candidate_rejects_lob_mismatch():
    with pytest.raises(CatalogValidationError):
        validate_candidate(VALID_ISSUE_CODE, "Payment", "HoganToAlfaSync")


def test_validate_candidate_rejects_service_area_mismatch():
    with pytest.raises(CatalogValidationError):
        validate_candidate(VALID_ISSUE_CODE, "LoanAdmin", "Boarding")

import pytest
from fastapi.testclient import TestClient

from query_intake.api import app, get_vector_store
from query_intake.models import VectorSearchCandidate

VALID_ISSUE_CODE = "PhoneNumber_Not_Updated_In_Alfa_From_Hogan"


class FakeVectorStore:
    def __init__(self, candidates: list[VectorSearchCandidate]):
        self._candidates = candidates

    def find_candidates(self, query_text, lob_filter=None, service_area_filter=None, top_k=3):
        return self._candidates


@pytest.fixture
def client_with_candidate():
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore(
        [VectorSearchCandidate(issue_code=VALID_ISSUE_CODE, lob="LoanAdmin", service_area="HoganToAlfaSync", score=0.87)]
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_no_candidates():
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore([])
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_extract_fully_inferred(client_with_candidate):
    response = client_with_candidate.post(
        "/query-intake/extract",
        json={"query_text": "phone update for ECN 395769222219117 failed on 20260304"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["issue_candidate"]["issue_code"] == VALID_ISSUE_CODE
    assert body["issue_candidate"]["lob_source"] == "inferred"
    assert body["issue_candidate"]["service_area_source"] == "inferred"
    assert body["issue_candidate"]["confidence_score"] == 0.87
    assert "account_number" in body["missing_required_fields"]
    assert "transaction_date" not in body["missing_required_fields"]


def test_extract_respects_explicit_lob_and_service_area(client_with_candidate):
    response = client_with_candidate.post(
        "/query-intake/extract",
        json={
            "query_text": "phone update failed",
            "selected_lob": "LoanAdmin",
            "selected_service_area": "HoganToAlfaSync",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["issue_candidate"]["lob_source"] == "explicit_ui"
    assert body["issue_candidate"]["service_area_source"] == "explicit_ui"


def test_extract_rejects_unknown_lob(client_with_candidate):
    response = client_with_candidate.post(
        "/query-intake/extract",
        json={"query_text": "phone update failed", "selected_lob": "NotARealLob"},
    )
    assert response.status_code == 400


def test_extract_returns_422_when_no_candidates(client_with_no_candidates):
    response = client_with_no_candidates.post(
        "/query-intake/extract",
        json={"query_text": "something completely unrelated"},
    )
    assert response.status_code == 422


def test_extract_missing_transaction_date_flagged():
    app.dependency_overrides[get_vector_store] = lambda: FakeVectorStore(
        [VectorSearchCandidate(issue_code=VALID_ISSUE_CODE, lob="LoanAdmin", service_area="HoganToAlfaSync", score=0.9)]
    )
    client = TestClient(app)
    response = client.post(
        "/query-intake/extract",
        json={"query_text": "ECN 395769222219117 account number 4471228 phone update failed"},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert "transaction_date" in response.json()["missing_required_fields"]


def test_confirm_returns_final_schema_with_exact_field_names():
    client = TestClient(app)
    response = client.post(
        "/query-intake/confirm",
        json={
            "correlation_id": None,
            "ecn": "395769222219117",
            "account_number": "4471228",
            "issue_code": VALID_ISSUE_CODE,
            "lob": "LoanAdmin",
            "service_area": "HoganToAlfaSync",
            "transaction_date": "20260304",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "CorrelaionId": None,
        "EnterpriseCustomerNumber": "395769222219117",
        "AccountNumber": "4471228",
        "IssueCode": VALID_ISSUE_CODE,
        "LOB": "LoanAdmin",
        "ServiceArea": "HoganToAlfaSync",
        "TransactionDate": "20260304",
    }


def test_confirm_rejects_catalog_mismatch():
    client = TestClient(app)
    response = client.post(
        "/query-intake/confirm",
        json={
            "ecn": "395769222219117",
            "account_number": "4471228",
            "issue_code": VALID_ISSUE_CODE,
            "lob": "LoanAdmin",
            "service_area": "Boarding",  # wrong service area for this issue code
            "transaction_date": "20260304",
        },
    )
    assert response.status_code == 422


def test_confirm_rejects_unconfirmed_date_format():
    client = TestClient(app)
    response = client.post(
        "/query-intake/confirm",
        json={
            "ecn": "395769222219117",
            "account_number": "4471228",
            "issue_code": VALID_ISSUE_CODE,
            "lob": "LoanAdmin",
            "service_area": "HoganToAlfaSync",
            "transaction_date": "March 4, 2026",
        },
    )
    assert response.status_code == 400


def test_confirm_rejects_blank_ecn():
    client = TestClient(app)
    response = client.post(
        "/query-intake/confirm",
        json={
            "ecn": "   ",
            "account_number": "4471228",
            "issue_code": VALID_ISSUE_CODE,
            "lob": "LoanAdmin",
            "service_area": "HoganToAlfaSync",
            "transaction_date": "20260304",
        },
    )
    assert response.status_code == 400

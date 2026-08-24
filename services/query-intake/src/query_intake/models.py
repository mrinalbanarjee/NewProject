"""Pydantic contracts for the query-intake service.

Two distinct shapes on purpose: the *candidate* shape (shown to a human for
confirmation, carries a confidence score) and the *confirmed* shape (the final
schema, produced only after human confirmation, never carries a score).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExtractedIdentifiers(BaseModel):
    """Deterministic, regex-based extraction results - never LLM-transcribed."""

    correlation_id: str | None = None
    ecn: str | None = None
    account_number: str | None = None
    raw_date_text: str | None = None


DateStatus = Literal[
    "missing",  # not provided - UI must prompt (TransactionDate is mandatory)
    "valid_no_confirm_needed",  # already YYYYMMDD
    "needs_confirmation",  # parsed from another format - human must confirm before it's written in
    "invalid_needs_reprompt",  # unparseable - ask the user for a correct date, don't guess
]


class DateResolution(BaseModel):
    raw_input: str | None = None
    normalized: str | None = None  # YYYYMMDD, set when status is valid_no_confirm_needed or needs_confirmation
    status: DateStatus
    message: str | None = None  # human-readable reason, populated for invalid_needs_reprompt


FieldSource = Literal["explicit_ui", "inferred"]


class IssueCandidate(BaseModel):
    """Vector-store output shown to the human for confirmation. Score never persists past this point."""

    issue_code: str
    lob: str
    service_area: str
    lob_source: FieldSource
    service_area_source: FieldSource
    confidence_score: float = Field(ge=0.0, le=1.0)


class ExtractResponse(BaseModel):
    """Result of POST /query-intake/extract - everything needed to render the confirm step."""

    identifiers: ExtractedIdentifiers
    issue_candidate: IssueCandidate
    date_resolution: DateResolution
    missing_required_fields: list[Literal["ecn", "account_number", "transaction_date"]]


class ConfirmRequest(BaseModel):
    """Input to POST /query-intake/confirm - the human-approved values."""

    correlation_id: str | None = None
    ecn: str
    account_number: str
    issue_code: str
    lob: str
    service_area: str
    transaction_date: str  # YYYYMMDD, already resolved/confirmed client-side


class VectorSearchCandidate(BaseModel):
    """Raw result from the vector store, before catalog validation."""

    issue_code: str
    lob: str
    service_area: str
    score: float


class IssueCatalogRecord(BaseModel):
    """
    Mongo document shape for the IssueCatalog collection (the "separate code to
    update the vector store" writes these). Full future field set defined now so
    the schema doesn't need migrating later - audit_collections/mongo_query_plan/
    splunk_queries/playbook/jira_board are populated by later pieces of work and
    stay blank until then.
    """

    issue_code: str
    lob: str
    service_area: str
    description: str  # the text embedded for vector search

    audit_collections: list[str] | None = None
    mongo_query_plan: list[dict] | None = None
    splunk_queries: list[str] | None = None
    playbook: dict | None = None
    jira_board: dict | None = None


class ConfirmedIssueDetails(BaseModel):
    """
    Final schema - field names/casing match the agreed contract exactly, including
    the CorrelaionId spelling (kept verbatim per the confirmed spec, not a typo here).
    """

    model_config = ConfigDict(populate_by_name=True)

    correlation_id: str | None = Field(default=None, alias="CorrelaionId")
    ecn: str = Field(alias="EnterpriseCustomerNumber")
    account_number: str = Field(alias="AccountNumber")
    issue_code: str = Field(alias="IssueCode")
    lob: str = Field(alias="LOB")
    service_area: str = Field(alias="ServiceArea")
    transaction_date: str = Field(alias="TransactionDate")

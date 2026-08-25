"""Output shapes returned by the tools - what the LLM (and any future API layer) sees."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MismatchAttribute(BaseModel):
    field_name: str
    key_name: str
    comment: str
    account_number: str | None = None
    is_cuac_code_matched: bool | None = None


class CustomerMismatch(BaseModel):
    ecn: str
    third_party_number: str
    mismatches: list[MismatchAttribute]


class BoardingStatus(BaseModel):
    account_number: str
    correlation_id: str
    succeeded: bool
    summary: str
    event_time: str


class DependentFailure(BaseModel):
    correlation_id: str
    update_type: str
    raw_request_message_type: str
    description: str
    event_time_stamp: str


class AccountRootCause(BaseModel):
    ecn: str
    account_number: str
    compare_comment: str
    is_cuac_code_matched: bool | None
    primary_boarding_status: BoardingStatus | None
    dependent_failures: list[DependentFailure]


class DiagnosticEntry(BaseModel):
    """
    One classified failure - shape and field names (camelCase) match the
    fixed contract this feeds downstream (the reprocess-script generator,
    and any external tooling), so this is the one model in the codebase that
    intentionally keeps camelCase over the JSON boundary rather than
    aliasing to snake_case.
    """

    model_config = ConfigDict(populate_by_name=True)

    correlation_id: str = Field(alias="correlationId")
    request_message_type: str = Field(alias="requestMessageType")
    event_timestamp: str = Field(alias="eventTimestamp")
    failure_reason: str = Field(alias="failureReason")
    can_be_reprocessed: bool = Field(alias="canBeReprocessed")
    recommendation: str


class DiagnosticsResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    diagnostics: list[DiagnosticEntry]


class AccountDiagnostics(BaseModel):
    """One account's classified dependent failures, plus enough about the
    primary boarding event to label and target it in a reprocess script."""

    model_config = ConfigDict(populate_by_name=True)

    ecn: str
    account_number: str = Field(alias="accountNumber")
    primary_correlation_id: str | None = Field(alias="primaryCorrelationId", default=None)
    primary_succeeded: bool | None = Field(alias="primarySucceeded", default=None)
    primary_summary: str | None = Field(alias="primarySummary", default=None)
    diagnostics: list[DiagnosticEntry]

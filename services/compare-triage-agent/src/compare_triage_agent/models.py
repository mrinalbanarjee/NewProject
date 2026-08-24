"""Output shapes returned by the tools - what the LLM (and any future API layer) sees."""

from __future__ import annotations

from pydantic import BaseModel


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
    succeeded: bool
    summary: str
    event_time: str


class DependentFailure(BaseModel):
    correlation_id: str
    update_type: str
    description: str
    event_time_stamp: str


class AccountRootCause(BaseModel):
    ecn: str
    account_number: str
    compare_comment: str
    is_cuac_code_matched: bool | None
    primary_boarding_status: BoardingStatus | None
    dependent_failures: list[DependentFailure]

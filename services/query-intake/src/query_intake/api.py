"""
FastAPI endpoints for the query-intake step:

  POST /query-intake/extract  - raw query text in, candidate shape out (with a
                                 confidence score, for a human to confirm)
  POST /query-intake/confirm  - human-approved values in, final schema out
                                 (never carries a score - its job is done)

Every value that reaches /confirm is re-validated against the catalog server-side,
even though it should already have passed through /extract - the confirm step must
not trust client-submitted values just because they look like they came from a
prior step.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from query_intake import catalog, extraction
from query_intake.catalog import CatalogValidationError
from query_intake.date_parsing import resolve_date
from query_intake.embeddings import VoyageEmbeddingProvider
from query_intake.env import require_env
from query_intake.models import ConfirmedIssueDetails, ConfirmRequest, ExtractResponse, IssueCandidate
from query_intake.vector_store import IssueVectorStore, VectorStoreConfig

app = FastAPI(title="query-intake")


@lru_cache
def get_vector_store() -> IssueVectorStore:
    config = VectorStoreConfig()
    embeddings = VoyageEmbeddingProvider(api_key=require_env("VOYAGE_API_KEY"))
    return IssueVectorStore(config, embeddings)


class ExtractRequest(BaseModel):
    query_text: str
    selected_lob: str | None = None
    selected_service_area: str | None = None


@app.post("/query-intake/extract", response_model=ExtractResponse)
def extract(request: ExtractRequest, vector_store: IssueVectorStore = Depends(get_vector_store)) -> ExtractResponse:
    if request.selected_lob is not None and not catalog.is_known_lob(request.selected_lob):
        raise HTTPException(status_code=400, detail=f"Unknown LOB: '{request.selected_lob}'.")
    if request.selected_service_area is not None:
        if request.selected_lob is None:
            raise HTTPException(status_code=400, detail="selected_service_area requires selected_lob.")
        if not catalog.is_known_service_area(request.selected_lob, request.selected_service_area):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown service area '{request.selected_service_area}' for LOB '{request.selected_lob}'.",
            )

    identifiers = extraction.extract_identifiers(request.query_text)
    date_resolution = resolve_date(identifiers.raw_date_text)

    candidates = vector_store.find_candidates(
        request.query_text,
        lob_filter=request.selected_lob,
        service_area_filter=request.selected_service_area,
        top_k=1,
    )
    if not candidates:
        raise HTTPException(
            status_code=422,
            detail="No matching issue code found for this query - try rephrasing, or select a LOB/service area explicitly.",
        )
    top = candidates[0]

    final_lob = request.selected_lob or top.lob
    final_service_area = request.selected_service_area or top.service_area

    try:
        catalog.validate_candidate(top.issue_code, final_lob, final_service_area)
    except CatalogValidationError as exc:
        # Defense in depth: the vector search was filtered to match, so this should
        # not normally happen - if it does, it's a stale index or a filter bug, not
        # a value worth passing downstream regardless.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    issue_candidate = IssueCandidate(
        issue_code=top.issue_code,
        lob=final_lob,
        service_area=final_service_area,
        lob_source="explicit_ui" if request.selected_lob else "inferred",
        service_area_source="explicit_ui" if request.selected_service_area else "inferred",
        confidence_score=top.score,
    )

    missing: list[str] = []
    if not identifiers.ecn:
        missing.append("ecn")
    if not identifiers.account_number:
        missing.append("account_number")
    if date_resolution.status in ("missing", "invalid_needs_reprompt"):
        missing.append("transaction_date")

    return ExtractResponse(
        identifiers=identifiers,
        issue_candidate=issue_candidate,
        date_resolution=date_resolution,
        missing_required_fields=missing,  # type: ignore[arg-type]
    )


@app.post("/query-intake/confirm", response_model=ConfirmedIssueDetails, response_model_by_alias=True)
def confirm(request: ConfirmRequest) -> ConfirmedIssueDetails:
    if not request.ecn.strip():
        raise HTTPException(status_code=400, detail="ecn is required.")
    if not request.account_number.strip():
        raise HTTPException(status_code=400, detail="account_number is required.")

    try:
        catalog.validate_candidate(request.issue_code, request.lob, request.service_area)
    except CatalogValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    date_check = resolve_date(request.transaction_date)
    if date_check.status != "valid_no_confirm_needed":
        raise HTTPException(
            status_code=400,
            detail=f"transaction_date must already be a confirmed YYYYMMDD value; got '{request.transaction_date}'.",
        )

    return ConfirmedIssueDetails(
        correlation_id=request.correlation_id,
        ecn=request.ecn,
        account_number=request.account_number,
        issue_code=request.issue_code,
        lob=request.lob,
        service_area=request.service_area,
        transaction_date=request.transaction_date,
    )

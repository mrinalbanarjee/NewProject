"""
Known LOB / ServiceArea / IssueCode values - the fail-closed check the vector
store's output must pass before anything downstream trusts it. A nearest-neighbor
match is a guess; this is what turns it into a validated fact.

POC scope is Loan Admin only, per the PRD. Note on the one seeded issue code: the
original spec's example name was "PhoneNumber_Not_Updated_In_Hogan_From_Alfa", but
by the project's own naming convention that describes the *AlfaToHoganSync*
direction (a Hogan-side gap caused by an Alfa-originated change). The entry below
is deliberately named the other way round - "..._In_Alfa_From_Hogan" - because it's
anchored to what's actually built: HoganToAlfaSync, OXCU054, the existing
DependencyResolver/StalenessChecker. Flagging this rather than reusing the example
verbatim, since the two directions are not interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass


class CatalogValidationError(Exception):
    """Raised when a vector-store (or UI-selected) value doesn't match a real catalog entry."""


@dataclass(frozen=True)
class IssueCatalogEntry:
    issue_code: str
    lob: str
    service_area: str
    description: str


KNOWN_LOBS: frozenset[str] = frozenset({"LoanAdmin"})

KNOWN_SERVICE_AREAS_BY_LOB: dict[str, frozenset[str]] = {
    "LoanAdmin": frozenset({"Boarding", "AlfaToHoganSync", "HoganToAlfaSync"}),
}

CATALOG: tuple[IssueCatalogEntry, ...] = (
    IssueCatalogEntry(
        issue_code="PhoneNumber_Not_Updated_In_Alfa_From_Hogan",
        lob="LoanAdmin",
        service_area="HoganToAlfaSync",
        description=(
            "A customer phone number changed in Hogan (OXCU054) but the "
            "notification updating Alfa failed or was never applied."
        ),
    ),
)

_BY_ISSUE_CODE: dict[str, IssueCatalogEntry] = {entry.issue_code: entry for entry in CATALOG}


def is_known_lob(lob: str) -> bool:
    return lob in KNOWN_LOBS


def is_known_service_area(lob: str, service_area: str) -> bool:
    return service_area in KNOWN_SERVICE_AREAS_BY_LOB.get(lob, frozenset())


def get_issue(issue_code: str) -> IssueCatalogEntry | None:
    return _BY_ISSUE_CODE.get(issue_code)


def validate_candidate(issue_code: str, lob: str, service_area: str) -> None:
    """Raises CatalogValidationError on any mismatch. Never trust a vector-store result unchecked."""
    entry = _BY_ISSUE_CODE.get(issue_code)
    if entry is None:
        raise CatalogValidationError(f"IssueCode '{issue_code}' is not in the catalog.")
    if entry.lob != lob:
        raise CatalogValidationError(f"IssueCode '{issue_code}' belongs to LOB '{entry.lob}', not '{lob}'.")
    if entry.service_area != service_area:
        raise CatalogValidationError(
            f"IssueCode '{issue_code}' belongs to service area '{entry.service_area}', not '{service_area}'."
        )

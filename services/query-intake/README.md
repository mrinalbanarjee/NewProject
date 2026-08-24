# query-intake

First slice of the AutoTriageSelf orchestration layer: takes a free-text user
query, extracts identifiers deterministically, resolves IssueCode/LOB/ServiceArea
via vector search against a curated catalog, and produces the confirmed structured
record the rest of the flow (see the orchestration proposal) builds on.

No generative LLM call in this slice - the only AI dependency is an embeddings
call for vector search. IssueCode/LOB/ServiceArea come from nearest-neighbor
retrieval + catalog validation, not LLM reasoning; identifiers (CorrelationId,
ECN, AccountNumber, dates) come from deterministic regex/parsing, not LLM
transcription.

## Requirements

- Python 3.11+
- A **MongoDB Atlas** cluster with a vector index configured on the `embedding`
  field of the issue-catalog collection. This will not work against a
  self-hosted/community MongoDB instance (e.g. the one `TriageApi.Api` points
  at) - Atlas Vector Search is an Atlas-only feature.
- A Voyage AI API key (default embeddings provider - swap `embeddings.py` if you
  want a different one; nothing else in the service depends on which).

## Setup

```bash
cd services/query-intake
python -m venv .venv
.venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
cp .env.example .env     # fill in MONGO_ATLAS_CONNECTION_STRING, MONGO_ATLAS_DATABASE_NAME, VOYAGE_API_KEY
```

## Seeding the vector store

Issue codes live in `query_intake/catalog.py` (single source of truth, also used
for server-side validation). To push them into the vector store:

```bash
python scripts/update_vector_store.py --dry-run   # preview, no writes, no credentials needed
python scripts/update_vector_store.py              # actually upserts
```

The catalog collection's full record shape (`IssueCatalogRecord`) already has
fields for audit-collection list, Mongo query plan, Splunk queries, playbook, and
JIRA board mapping - all left blank for now, populated as those pieces of the
larger design get built, so the schema won't need migrating later.

## Running

```bash
uvicorn query_intake.api:app --reload
```

## Endpoints

- `POST /query-intake/extract` — `{query_text, selected_lob?, selected_service_area?}`
  → identifiers, an issue candidate (IssueCode always inferred; LOB/ServiceArea
  inferred only if not explicitly selected), a date resolution, and which
  required fields are still missing. Every field in the response is meant to
  drive a human confirmation step before anything proceeds - this endpoint
  never assumes its own output is correct.
- `POST /query-intake/confirm` — the human-approved values → the final schema
  (`CorrelaionId`, `EnterpriseCustomerNumber`, `AccountNumber`, `IssueCode`,
  `LOB`, `ServiceArea`, `TransactionDate`). Re-validates against the catalog and
  re-checks the date format server-side rather than trusting that the client
  actually went through `/extract` first.

## Known scope notes

- `CorrelaionId` keeps that exact spelling in the final schema - it's the agreed
  contract, not a bug in this code.
- ECN and AccountNumber are both mandatory; CorrelationId is optional.
- TransactionDate: `YYYYMMDD` as given needs no confirmation; a parseable
  alternate format gets normalized but must be confirmed before being written
  in; unparseable text is rejected and the user is asked again.
- The one seeded catalog entry (`PhoneNumber_Not_Updated_In_Alfa_From_Hogan`) is
  named opposite to the original example in the requirements doc
  (`..._In_Hogan_From_Alfa`) - by the project's own HoganToAlfaSync/
  AlfaToHoganSync naming convention, the original example describes the other
  direction. This entry is anchored to what's actually built (OXCU054,
  `TriageApi.Core`'s `DependencyResolver`/`StalenessChecker`).
- ECN/AccountNumber extraction regexes are a best-effort default, not validated
  against a representative sample of real user queries yet.

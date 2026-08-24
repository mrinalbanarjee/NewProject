"""
Separate code path for updating the vector store, per the agreed spec - this never
runs as part of request handling, only as a deliberate, human-run step.

Issue codes are sourced from query_intake.catalog.CATALOG (the same list the
/extract and /confirm endpoints validate against) so there's one place that
defines "what issue codes exist," not two lists that can drift apart. Each
catalog entry becomes an IssueCatalogRecord with the audit-collection/query-plan/
Splunk/playbook/JIRA fields left blank, per the current scope.

Usage:
    python scripts/update_vector_store.py           # upserts every catalog entry
    python scripts/update_vector_store.py --dry-run  # prints what would be upserted, no writes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from query_intake import catalog  # noqa: E402
from query_intake.embeddings import VoyageEmbeddingProvider  # noqa: E402
from query_intake.env import require_env  # noqa: E402
from query_intake.models import IssueCatalogRecord  # noqa: E402
from query_intake.vector_store import IssueVectorStore, VectorStoreConfig  # noqa: E402


def build_records() -> list[IssueCatalogRecord]:
    return [
        IssueCatalogRecord(
            issue_code=entry.issue_code,
            lob=entry.lob,
            service_area=entry.service_area,
            description=entry.description,
            # Left blank deliberately - populated by later pieces of work.
            audit_collections=None,
            mongo_query_plan=None,
            splunk_queries=None,
            playbook=None,
            jira_board=None,
        )
        for entry in catalog.CATALOG
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be upserted, without writing.")
    args = parser.parse_args()

    load_dotenv()
    records = build_records()

    if args.dry_run:
        print(f"Would upsert {len(records)} issue catalog record(s):")
        for record in records:
            print(f"  - {record.issue_code}  (LOB={record.lob}, ServiceArea={record.service_area})")
        return

    config = VectorStoreConfig()
    embeddings = VoyageEmbeddingProvider(api_key=require_env("VOYAGE_API_KEY"))
    store = IssueVectorStore(config, embeddings)

    for record in records:
        store.upsert_issue_record(record)
        print(f"Upserted: {record.issue_code}")

    print(f"Done - {len(records)} record(s) upserted.")


if __name__ == "__main__":
    main()

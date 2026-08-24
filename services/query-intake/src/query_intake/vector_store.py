"""MongoDB Atlas Vector Search client for the issue catalog.

Requires an Atlas cluster with a vector index configured on the `embedding` field
of the issue-catalog collection - this will not work against a self-hosted/
community MongoDB instance (e.g. the one TriageApi.Api points at).
"""

from __future__ import annotations

import os

from pymongo import MongoClient
from pymongo.collection import Collection

from query_intake.embeddings import EmbeddingProvider
from query_intake.env import require_env
from query_intake.models import IssueCatalogRecord, VectorSearchCandidate


class VectorStoreConfig:
    def __init__(self) -> None:
        self.connection_string = require_env("MONGO_ATLAS_CONNECTION_STRING")
        self.database_name = require_env("MONGO_ATLAS_DATABASE_NAME")
        self.collection_name = os.environ.get("MONGO_ATLAS_ISSUE_CATALOG_COLLECTION", "IssueCatalog")
        self.vector_index_name = os.environ.get("MONGO_ATLAS_VECTOR_INDEX_NAME", "issue_catalog_vector_index")


class IssueVectorStore:
    def __init__(self, config: VectorStoreConfig, embeddings: EmbeddingProvider):
        self._config = config
        self._embeddings = embeddings
        self._client: MongoClient = MongoClient(config.connection_string)
        self._collection: Collection = self._client[config.database_name][config.collection_name]

    def find_candidates(
        self,
        query_text: str,
        lob_filter: str | None = None,
        service_area_filter: str | None = None,
        top_k: int = 3,
    ) -> list[VectorSearchCandidate]:
        query_vector = self._embeddings.embed_query(query_text)

        vector_search_stage: dict = {
            "index": self._config.vector_index_name,
            "path": "embedding",
            "queryVector": query_vector,
            # Atlas recommends numCandidates well above limit for recall; scale with top_k.
            "numCandidates": max(top_k * 20, 50),
            "limit": top_k,
        }

        filter_clauses = [
            {"lob": value} for value in [lob_filter] if value
        ] + [
            {"service_area": value} for value in [service_area_filter] if value
        ]
        if filter_clauses:
            vector_search_stage["filter"] = (
                {"$and": filter_clauses} if len(filter_clauses) > 1 else filter_clauses[0]
            )

        pipeline = [
            {"$vectorSearch": vector_search_stage},
            {
                "$project": {
                    "_id": 0,
                    "issue_code": 1,
                    "lob": 1,
                    "service_area": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        results = self._collection.aggregate(pipeline)
        return [
            VectorSearchCandidate(
                issue_code=doc["issue_code"],
                lob=doc["lob"],
                service_area=doc["service_area"],
                score=doc["score"],
            )
            for doc in results
        ]

    def upsert_issue_record(self, record: IssueCatalogRecord) -> None:
        """Used by the separate vector-store-update script (scripts/update_vector_store.py)."""
        embedding = self._embeddings.embed_documents([record.description])[0]
        document = record.model_dump()
        document["embedding"] = embedding
        self._collection.update_one(
            {"issue_code": record.issue_code},
            {"$set": document},
            upsert=True,
        )

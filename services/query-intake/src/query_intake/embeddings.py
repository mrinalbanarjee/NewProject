"""
Embedding provider abstraction. The only generative-AI dependency this service
has left - identifier extraction is deterministic regex, and IssueCode/LOB/
ServiceArea come from vector similarity + catalog validation, not an LLM call.

Defaults to Voyage AI (Anthropic's recommended embeddings partner) since the
project's already committed to a public/Anthropic-adjacent stack for this phase.
Swappable: nothing outside this module knows which provider is in use.
"""

from __future__ import annotations

from typing import Protocol

import voyageai


class EmbeddingProvider(Protocol):
    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VoyageEmbeddingProvider:
    def __init__(self, api_key: str, model: str = "voyage-3.5"):
        self._client = voyageai.Client(api_key=api_key)
        self._model = model

    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed([text], model=self._model, input_type="query")
        return result.embeddings[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(texts, model=self._model, input_type="document")
        return result.embeddings

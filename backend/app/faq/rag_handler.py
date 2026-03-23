"""
RAG Handler - backward-compatible wrapper around the modular RAG provider system.

For new code, use `from app.faq.rag import get_rag_provider` directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from app.faq.rag import get_rag_provider, RAGResult


@dataclass
class Document:
    """A document chunk retrieved from the vector store (legacy compat)."""

    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    source: str = ""


class RAGHandler:
    """
    Backward-compatible wrapper that delegates to the modular RAG provider.
    """

    async def search(self, query: str, top_k: int = 5) -> List[Document]:
        provider = get_rag_provider()
        if provider is None:
            raise NotImplementedError("RAG is not configured. Set RAG_PROVIDER env var.")

        results = await provider.search(query, top_k=top_k)
        return [
            Document(
                content=r.content,
                score=r.score,
                source=r.source,
                metadata=r.metadata,
            )
            for r in results
        ]

    async def generate(self, query: str, context: List[Document]) -> str:
        raise NotImplementedError("Use AI handler for generation. RAG provides retrieval only.")

    async def index_document(self, content: str, metadata: dict | None = None) -> str:
        raise NotImplementedError("Document indexing is managed via Dify dashboard.")

    async def delete_document(self, document_id: str) -> bool:
        raise NotImplementedError("Document deletion is managed via Dify dashboard.")


# Module-level singleton
rag_handler = RAGHandler()

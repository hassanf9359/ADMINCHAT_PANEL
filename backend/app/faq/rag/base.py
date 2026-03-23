"""
RAG Provider - Abstract base class for Retrieval-Augmented Generation providers.

Modular design: each RAG backend (Dify, pgvector, etc.) implements RAGProvider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RAGResult:
    """A single result from a RAG knowledge base search."""

    content: str
    score: float = 0.0
    source: str = ""
    metadata: dict = field(default_factory=dict)


class RAGProvider(ABC):
    """Abstract base class for RAG providers."""

    @abstractmethod
    async def search(self, query: str, top_k: int = 3) -> List[RAGResult]:
        """
        Search the knowledge base for relevant documents.

        Args:
            query: The user's question.
            top_k: Number of top results to return.

        Returns:
            List of RAGResult objects sorted by relevance.
        """

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass

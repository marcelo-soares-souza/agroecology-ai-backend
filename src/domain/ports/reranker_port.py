from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.retrieval_result import RetrievedChunk


class RerankerPort(ABC):
    """Port for re-ranking retrieval results.

    Re-scores a candidate set of retrieved chunks to improve result
    quality beyond the initial similarity score.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Re-rank a list of retrieved chunks by relevance to the query.

        Args:
            query: The search query.
            documents: The candidate chunks to re-rank.
            top_k: Maximum number of results to return.

        Returns:
            The re-ranked list of chunks, truncated to top_k.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the reranker model."""

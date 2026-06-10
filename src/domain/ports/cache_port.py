from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.dto.answer_result import AnswerResult


class CachePort(ABC):
    """Port for caching Q&A results.

    Caches answers keyed by question and retrieval parameters
    to avoid redundant LLM calls and vector searches.

    Attributes:
        enabled: Whether caching is active.
    """

    enabled: bool

    @abstractmethod
    def get(self, question: str, top_k: int = 0) -> AnswerResult | None:
        """Retrieve a cached answer for the given question.

        Args:
            question: The user's question.
            top_k: The retrieval top_k used (for cache keying).

        Returns:
            The cached AnswerResult, or None if not found.
        """

    @abstractmethod
    def set(self, question: str, result: AnswerResult, top_k: int = 0) -> None:
        """Store an answer in the cache.

        Args:
            question: The user's question.
            result: The answer to cache.
            top_k: The retrieval top_k used.
        """

    @abstractmethod
    def hit_count(self) -> int:
        """Return the number of cache hits since initialization.

        Returns:
            The total cache hit count.
        """

    @abstractmethod
    def close(self) -> None:
        """Close the cache and release any resources."""

    @abstractmethod
    def set_index_version(self, version: str) -> None:
        """Update the index version used to compose cache keys.

        Args:
            version: The new index version string.
        """

    @abstractmethod
    def invalidate_all(self) -> None:
        """Clear all cache entries for the current index version."""

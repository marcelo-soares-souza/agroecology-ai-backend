from abc import ABC, abstractmethod

from src.domain.dto.answer_result import AnswerResult


class CachePort(ABC):
    enabled: bool

    @abstractmethod
    def get(self, question: str, top_k: int = 0) -> AnswerResult | None: ...

    @abstractmethod
    def set(self, question: str, result: AnswerResult, top_k: int = 0) -> None: ...

    @abstractmethod
    def hit_count(self) -> int: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def set_index_version(self, version: str) -> None:
        """Update the index version used to compose cache keys."""

    @abstractmethod
    def invalidate_all(self) -> None:
        """Clear all cache entries for the current index version."""

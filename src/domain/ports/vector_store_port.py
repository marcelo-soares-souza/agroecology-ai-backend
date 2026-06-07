from abc import ABC, abstractmethod
from typing import Any

from src.domain.dto.retrieval_result import IndexedChunk, RetrievedChunk


class VectorStorePort(ABC):
    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]: ...

    @abstractmethod
    def index_exists(self) -> bool: ...

    @abstractmethod
    def build_index(self, rows: list[IndexedChunk], dimension: int) -> None: ...

    @abstractmethod
    def add_rows(self, rows: list[IndexedChunk]) -> None: ...

    @abstractmethod
    def delete_by_prefix(self, id_prefix: str) -> None: ...

    @abstractmethod
    def get_all_rows(self) -> list[RetrievedChunk]: ...

    @abstractmethod
    def count_chunks(self) -> int: ...

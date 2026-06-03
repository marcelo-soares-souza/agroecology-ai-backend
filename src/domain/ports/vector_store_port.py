from abc import ABC, abstractmethod
from typing import Any


class VectorStorePort(ABC):
    @abstractmethod
    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    def index_exists(self) -> bool: ...

    @abstractmethod
    def build_index(self, rows: list[dict[str, Any]], dimension: int) -> None: ...

    @abstractmethod
    def get_all_rows(self) -> list[dict[str, Any]]: ...

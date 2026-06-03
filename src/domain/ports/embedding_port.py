from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]: ...

    @abstractmethod
    def get_dimension(self) -> int: ...

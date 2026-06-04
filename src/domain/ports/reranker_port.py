from abc import ABC, abstractmethod


class RerankerPort(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[dict], top_k: int) -> list[dict]: ...

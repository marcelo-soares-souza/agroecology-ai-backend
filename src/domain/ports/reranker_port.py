from abc import ABC, abstractmethod

from src.domain.dto.retrieval_result import RetrievedChunk


class RerankerPort(ABC):
    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]: ...

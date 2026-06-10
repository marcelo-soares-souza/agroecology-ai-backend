from abc import ABC, abstractmethod


class BM25Port(ABC):
    @abstractmethod
    def build_index(self, corpus: list[list[str]]) -> None: ...
    @abstractmethod
    def get_scores(self, query_tokens: list[str]) -> list[float]: ...

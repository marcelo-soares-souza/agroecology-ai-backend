from rank_bm25 import BM25Okapi

from src.domain.ports.bm25_port import BM25Port


class BM25Impl(BM25Port):
    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None

    def build_index(self, corpus: list[list[str]]) -> None:
        self._bm25 = BM25Okapi(corpus)

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        if self._bm25 is None:
            return []
        return list(self._bm25.get_scores(query_tokens))

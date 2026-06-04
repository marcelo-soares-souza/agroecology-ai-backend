from __future__ import annotations

from rank_bm25 import BM25Okapi

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import BM25_TOP_K, HYBRID_TOP_K, RERANK_TOP_K, SIMILARITY_TOP_K


class RetrieverService:
    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbeddingPort,
        reranker: RerankerPort | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._reranker = reranker

    def hybrid_search(self, query: str, top_k: int = HYBRID_TOP_K) -> list[dict]:
        vec_results = self._vector_search(query, top_k=SIMILARITY_TOP_K)
        bm25_results = self._bm25_search(query, top_k=BM25_TOP_K)

        if not bm25_results:
            return vec_results[:top_k]

        fused = self._rrf_fusion(vec_results, bm25_results)

        if self._reranker is not None:
            candidates = fused[:RERANK_TOP_K]
            return self._reranker.rerank(query, candidates, top_k)

        return fused[:top_k]

    def _vector_search(self, query: str, top_k: int) -> list[dict]:
        query_vec = self._embedder.embed_query(query)
        return self._vector_store.search(query_vec, top_k=top_k)

    def _bm25_search(self, query: str, top_k: int) -> list[dict]:
        all_rows = self._vector_store.get_all_rows()
        texts = [str(r["text"]) for r in all_rows]
        bm25 = BM25Okapi([t.lower().split() for t in texts])
        scores = bm25.get_scores(query.lower().split())
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_k]:
            row = dict(all_rows[idx])
            row["_distance"] = float(score)
            row["_search_type"] = "bm25"
            results.append(row)
        return results

    @staticmethod
    def _rrf_fusion(
        vec: list[dict],
        bm25: list[dict],
        k: int = 60,
    ) -> list[dict]:
        scores: dict[str, float] = {}
        rows: dict[str, dict] = {}

        for rank, r in enumerate(vec):
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            rows[doc_id] = r
        for rank, r in enumerate(bm25):
            doc_id = r["id"]
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            rows[doc_id] = r

        sorted_ids = sorted(scores, key=lambda k: scores[k], reverse=True)
        return [
            {**dict(rows[doc_id]), "_rrf_score": scores[doc_id]}
            for doc_id in sorted_ids
        ]

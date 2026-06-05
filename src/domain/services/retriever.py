from __future__ import annotations

import logging
import time
from typing import Any

from rank_bm25 import BM25Okapi

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import (
    BM25_TOP_K,
    HYBRID_TOP_K,
    MMR_LAMBDA,
    RERANK_TOP_K,
    SIMILARITY_TOP_K,
)

logger = logging.getLogger("agroecology.retrieval")


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
        self._bm25: BM25Okapi | None = None
        self._bm25_texts: list[str] = []
        self._bm25_all_rows: list[dict] = []

    def _get_bm25(self) -> tuple[BM25Okapi, list[dict]]:
        if self._bm25 is None or not self._bm25_all_rows:
            self._bm25_all_rows = self._vector_store.get_all_rows()
            self._bm25_texts = [str(r["text"]) for r in self._bm25_all_rows]
            self._bm25 = BM25Okapi([t.lower().split() for t in self._bm25_texts])
            logger.info("bm25_cache_built chunks=%d", len(self._bm25_texts))
        return self._bm25, self._bm25_all_rows

    def invalidate_bm25_cache(self) -> None:
        self._bm25 = None
        self._bm25_texts = []
        self._bm25_all_rows = []
        logger.info("bm25_cache_invalidated")

    def hybrid_search(
        self,
        query: str,
        top_k: int = HYBRID_TOP_K,
        filters: dict[str, Any] | None = None,
    ) -> list[dict]:
        t0 = time.perf_counter()

        t1 = time.perf_counter()
        vec_results = self._vector_search(
            query, top_k=SIMILARITY_TOP_K, filters=filters
        )
        t_vec = round((time.perf_counter() - t1) * 1000, 2)

        t2 = time.perf_counter()
        bm25_results = self._bm25_search(query, top_k=BM25_TOP_K, filters=filters)
        t_bm25 = round((time.perf_counter() - t2) * 1000, 2)

        if not bm25_results:
            logger.info(
                "retrieval_completed step=vector_only vector_count=%d vec_ms=%s",
                len(vec_results[:top_k]),
                t_vec,
            )
            return vec_results[:top_k]

        t3 = time.perf_counter()
        fused = self._rrf_fusion(vec_results, bm25_results)
        t_rrf = round((time.perf_counter() - t3) * 1000, 2)

        if self._reranker is not None:
            t4 = time.perf_counter()
            candidates = fused[:top_k]
            results = self._reranker.rerank(query, candidates, RERANK_TOP_K)
            t_rerank = round((time.perf_counter() - t4) * 1000, 2)
        else:
            results = fused[:top_k]
            t_rerank = 0

        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        unique_docs = len({r.get("source", "") for r in results})
        logger.info(
            "retrieval_completed step=hybrid vector_count=%d bm25_count=%d rrf_candidates=%d final_count=%d unique_docs=%d vec_ms=%s bm25_ms=%s rrf_ms=%s rerank_ms=%s total_ms=%s",
            len(vec_results),
            len(bm25_results),
            len(fused),
            len(results),
            unique_docs,
            t_vec,
            t_bm25,
            t_rrf,
            t_rerank,
            total_ms,
        )

        results = self._mmr_diversify(results, MMR_LAMBDA)
        return results

    def _mmr_diversify(self, results: list[dict], lam: float) -> list[dict]:
        if not results or len(results) <= 1:
            return results

        selected: list[dict] = [results[0]]
        remaining = results[1:]

        while remaining and len(selected) < len(results):
            best_idx = 0
            best_score = float("-inf")

            for i, candidate in enumerate(remaining):
                relevance = float(
                    candidate.get("_rerank_score", candidate.get("_distance", 0))
                )
                max_sim = 0.0
                for s in selected:
                    same_doc = candidate.get("source", "") == s.get("source", "")
                    sim = 1.0 if same_doc else 0.0
                    if sim > max_sim:
                        max_sim = sim

                mmr = lam * relevance - (1.0 - lam) * max_sim
                if mmr > best_score:
                    best_score = mmr
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def _match_filters(row: dict, filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            row_val = row.get(key)
            if row_val is None:
                return False
            if isinstance(value, tuple) and len(value) == 2:
                if not (value[0] <= row_val <= value[1]):
                    return False
            elif row_val != value:
                return False
        return True

    def _vector_search(
        self, query: str, top_k: int, filters: dict[str, Any] | None = None
    ) -> list[dict]:
        query_vec = self._embedder.embed_query(query)
        return self._vector_store.search(query_vec, top_k=top_k, filters=filters)

    def _bm25_search(
        self, query: str, top_k: int, filters: dict[str, Any] | None = None
    ) -> list[dict]:
        bm25, all_rows = self._get_bm25()
        if not all_rows:
            return []
        scores = bm25.get_scores(query.lower().split())
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed:
            row = dict(all_rows[idx])
            if filters and not self._match_filters(row, filters):
                continue
            row["_distance"] = float(score)
            row["_search_type"] = "bm25"
            results.append(row)
            if len(results) >= top_k:
                break
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

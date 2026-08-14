from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.domain.dto.retrieval_result import RetrievedChunk
from src.domain.ports.bm25_port import BM25Port
from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.reranker_port import RerankerPort
from src.domain.ports.vector_store_port import VectorStorePort

logger = logging.getLogger("agroecology.retrieval")


@dataclass(frozen=True)
class BM25RuntimeStatus:
    state: str
    chunks: int
    generation: int
    last_prewarm_ms: float | None
    error: str | None


@dataclass(frozen=True)
class _BM25Snapshot:
    port: BM25Port
    rows: list[RetrievedChunk]
    generation: int


class RetrieverService:
    """Hybrid search service combining vector similarity, BM25, and reranking.

    Orchestrates retrieval through the vector store, embedding model, and
    optional reranker, fusing results with Reciprocal Rank Fusion and
    applying Maximal Marginal Relevance diversification.
    """

    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbeddingPort,
        bm25_factory: Callable[[], BM25Port],
        reranker: RerankerPort | None = None,
        bm25_top_k: int = 5,
        hybrid_top_k: int = 10,
        mmr_lambda: float = 0.7,
        similarity_top_k: int = 5,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._bm25_factory = bm25_factory
        self._reranker = reranker
        self._bm25_lock = threading.Lock()
        self._bm25_snapshot: _BM25Snapshot | None = None
        self._bm25_state = "cold"
        self._bm25_generation = 0
        self._bm25_last_prewarm_ms: float | None = None
        self._bm25_error: str | None = None
        self._bm25_top_k = bm25_top_k
        self._hybrid_top_k = hybrid_top_k
        self._mmr_lambda = mmr_lambda
        self._similarity_top_k = similarity_top_k

    def prewarm_bm25(self, generation: int | None = None) -> bool:
        with self._bm25_lock:
            target_generation = (
                self._bm25_generation if generation is None else generation
            )
            if target_generation != self._bm25_generation:
                return False
            self._bm25_state = "warming"
            self._bm25_error = None

        started_at = time.perf_counter()
        logger.info(
            "event=bm25_prewarm_started generation=%d",
            target_generation,
        )
        try:
            rows = self._vector_store.get_all_rows()
            bm25_port = self._bm25_factory()
            bm25_port.build_index([self._tokenize_bm25(row.text) for row in rows])
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            snapshot = _BM25Snapshot(
                port=bm25_port,
                rows=rows,
                generation=target_generation,
            )

            with self._bm25_lock:
                if target_generation != self._bm25_generation:
                    logger.info(
                        "event=bm25_prewarm_discarded generation=%d current_generation=%d chunks=%d duration_ms=%s",
                        target_generation,
                        self._bm25_generation,
                        len(rows),
                        duration_ms,
                    )
                    return False
                self._bm25_snapshot = snapshot
                self._bm25_state = "ready"
                self._bm25_last_prewarm_ms = duration_ms
                self._bm25_error = None

            logger.info(
                "event=bm25_prewarm_completed generation=%d chunks=%d duration_ms=%s",
                target_generation,
                len(rows),
                duration_ms,
            )
            return True
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            with self._bm25_lock:
                if target_generation == self._bm25_generation:
                    self._bm25_state = "error"
                    self._bm25_error = str(exc)
            logger.error(
                "event=bm25_prewarm_failed generation=%d duration_ms=%s error=%s",
                target_generation,
                duration_ms,
                exc,
            )
            raise

    def invalidate_bm25_cache(self) -> int:
        with self._bm25_lock:
            self._bm25_generation += 1
            generation = self._bm25_generation
            self._bm25_snapshot = None
            self._bm25_state = "warming"
            self._bm25_error = None
        logger.info("event=bm25_cache_invalidated generation=%d", generation)
        return generation

    def get_bm25_status(self) -> BM25RuntimeStatus:
        with self._bm25_lock:
            snapshot = self._bm25_snapshot
            return BM25RuntimeStatus(
                state=self._bm25_state,
                chunks=len(snapshot.rows) if snapshot is not None else 0,
                generation=self._bm25_generation,
                last_prewarm_ms=self._bm25_last_prewarm_ms,
                error=self._bm25_error,
            )

    def hybrid_search(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Perform hybrid retrieval combining vector and BM25 search.

        Runs both vector similarity and BM25 searches, fuses results via
        Reciprocal Rank Fusion, optionally re-ranks candidates, and applies
        MMR diversification for the final result set.

        Args:
            query: The search query.
            top_k: Desired number of internal reranked results.
            filters: Optional metadata filters applied to both search paths.

        Returns:
            A list of RetrievedChunk results ordered by relevance.
        """
        started_at = time.perf_counter()
        t0 = time.perf_counter()

        t1 = time.perf_counter()
        vec_results = self._vector_search(
            query, top_k=self._similarity_top_k, filters=filters
        )
        t_vec = round((time.perf_counter() - t1) * 1000, 2)

        t2 = time.perf_counter()
        bm25_results = self._bm25_search(query, top_k=self._bm25_top_k, filters=filters)
        t_bm25 = round((time.perf_counter() - t2) * 1000, 2)

        if not bm25_results:
            retrieval_wall_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info(
                "event=retrieval_completed step=vector_only vector_count=%d vec_ms=%s retrieval_wall_ms=%s",
                len(vec_results[:top_k]),
                t_vec,
                retrieval_wall_ms,
            )
            return vec_results[:top_k]

        t3 = time.perf_counter()
        fused = self._rrf_fusion(vec_results, bm25_results)
        t_rrf = round((time.perf_counter() - t3) * 1000, 2)

        if self._reranker is not None:
            t4 = time.perf_counter()
            candidate_count = max(self._hybrid_top_k, top_k * 2)
            candidates = fused[:candidate_count]
            results = self._reranker.rerank(query, candidates, top_k)
            t_rerank = round((time.perf_counter() - t4) * 1000, 2)
        else:
            candidate_count = 0
            results = fused[:top_k]
            t_rerank = 0

        total_ms = round((time.perf_counter() - t0) * 1000, 2)
        retrieval_wall_ms = round((time.perf_counter() - started_at) * 1000, 2)
        unique_docs = len({r.source for r in results})
        logger.info(
            "event=retrieval_completed step=hybrid vector_count=%d bm25_count=%d rrf_candidates=%d rerank_candidates=%d final_count=%d unique_docs=%d vec_ms=%s bm25_ms=%s rrf_ms=%s rerank_ms=%s total_ms=%s retrieval_wall_ms=%s",
            len(vec_results),
            len(bm25_results),
            len(fused),
            candidate_count,
            len(results),
            unique_docs,
            t_vec,
            t_bm25,
            t_rrf,
            t_rerank,
            total_ms,
            retrieval_wall_ms,
        )

        results = self._mmr_diversify(results, self._mmr_lambda)
        return results

    def _mmr_diversify(
        self,
        results: list[RetrievedChunk],
        lam: float,
    ) -> list[RetrievedChunk]:
        if not results or len(results) <= 1:
            return results

        selected: list[RetrievedChunk] = [results[0]]
        remaining = results[1:]

        while remaining and len(selected) < len(results):
            best_idx = 0
            best_score = float("-inf")

            for i, candidate in enumerate(remaining):
                relevance = float(candidate.rerank_score or candidate.distance or 0.0)
                max_sim = 0.0
                for s in selected:
                    same_doc = candidate.source == s.source
                    sim = 1.0 if same_doc else 0.0
                    max_sim = max(max_sim, sim)

                mmr = lam * relevance - (1.0 - lam) * max_sim
                if mmr > best_score:
                    best_score = mmr
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    @staticmethod
    def _match_filters(row: RetrievedChunk, filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            row_val = getattr(row, key, None)
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
    ) -> list[RetrievedChunk]:
        query_vec = self._embedder.embed_query(query)
        return self._vector_store.search(query_vec, top_k=top_k, filters=filters)

    def _bm25_search(
        self, query: str, top_k: int, filters: dict[str, Any] | None = None
    ) -> list[RetrievedChunk]:
        with self._bm25_lock:
            snapshot = self._bm25_snapshot
            state = self._bm25_state
            generation = self._bm25_generation

        if snapshot is None:
            logger.info(
                "event=bm25_vector_fallback_used state=%s generation=%d",
                state,
                generation,
            )
            return []
        all_rows = snapshot.rows
        scores = snapshot.port.get_scores(self._tokenize_bm25(query))
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[RetrievedChunk] = []
        for idx, score in indexed:
            row = all_rows[idx]
            if filters and not self._match_filters(row, filters):
                continue
            row = RetrievedChunk.from_dict(row.to_dict())
            row.distance = float(score)
            row.search_type = "bm25"
            results.append(row)
            if len(results) >= top_k:
                break
        return results

    @staticmethod
    def _tokenize_bm25(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    @staticmethod
    def _rrf_fusion(
        vec: list[RetrievedChunk],
        bm25_results: list[RetrievedChunk],
        k: int = 60,
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = {}
        rows: dict[str, RetrievedChunk] = {}

        for rank, r in enumerate(vec):
            doc_id = r.id
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            rows[doc_id] = r
        for rank, r in enumerate(bm25_results):
            doc_id = r.id
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
            rows[doc_id] = r

        sorted_ids = sorted(scores, key=lambda k: scores[k], reverse=True)
        results: list[RetrievedChunk] = []
        for doc_id in sorted_ids:
            row = RetrievedChunk.from_dict(rows[doc_id].to_dict())
            row.rrf_score = scores[doc_id]
            results.append(row)
        return results

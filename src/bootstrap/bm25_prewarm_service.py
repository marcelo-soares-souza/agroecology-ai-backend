from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from src.domain.services.retriever import RetrieverService

logger = logging.getLogger("agroecology.bootstrap")


class BM25PrewarmService:
    def __init__(self, retriever: RetrieverService) -> None:
        self._retriever = retriever
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="bm25-prewarm",
        )
        self._lock = threading.Lock()
        self._future: Future[None] | None = None
        self._requested_generation = retriever.get_bm25_status().generation
        self._closed = False

    def request(self) -> int | None:
        with self._lock:
            if self._closed:
                logger.warning("event=bm25_prewarm_rejected reason=service_closed")
                return None

            generation = self._retriever.invalidate_bm25_cache()
            self._requested_generation = generation
            already_running = self._future is not None
            if not already_running:
                self._future = self._executor.submit(self._run)

        logger.info(
            "event=bm25_prewarm_scheduled generation=%d coalesced=%s",
            generation,
            already_running,
        )
        return generation

    def _run(self) -> None:
        while True:
            with self._lock:
                if self._closed:
                    self._future = None
                    return
                generation = self._requested_generation

            try:
                self._retriever.prewarm_bm25(generation)
            except Exception:
                logger.exception(
                    "event=bm25_background_prewarm_failed generation=%d",
                    generation,
                )

            with self._lock:
                if self._closed:
                    self._future = None
                    return
                if generation == self._requested_generation:
                    self._future = None
                    return

            logger.info(
                "event=bm25_prewarm_restarting stale_generation=%d requested_generation=%d",
                generation,
                self._requested_generation,
            )

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True

        self._executor.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._future = None
        logger.info("event=bm25_prewarm_service_stopped")

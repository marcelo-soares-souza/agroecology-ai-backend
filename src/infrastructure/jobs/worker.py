from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable, Protocol

from src.domain.dto.document_result import MetadataExtractionResult

from src.infrastructure.persistence.queue_repository import QueueRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger(__name__)


class MetadataExtractionUseCase(Protocol):
    async def execute(self, doc_id: str) -> MetadataExtractionResult | None:
        pass


JobHandler = Callable[[dict, MetadataExtractionUseCase | None], None]

_HANDLERS: dict[str, JobHandler] = {}


def _register_handler(job_type: str):
    def decorator(fn):
        _HANDLERS[job_type] = fn
        return fn

    return decorator


@_register_handler("document.extract_metadata")
def _handle_extract_metadata(
    payload: dict, metadata_use_case: MetadataExtractionUseCase | None
) -> None:
    doc_id = payload["document_id"]
    log_event(logger, logging.INFO, "metadata_job_started", document_id=doc_id)

    try:

        async def _run():
            if metadata_use_case is None:
                log_event(
                    logger,
                    logging.WARNING,
                    "metadata_job_aborted",
                    reason="metadata_use_case_not_available",
                    document_id=doc_id,
                )
                return

            result = await metadata_use_case.execute(doc_id)
            if result:
                log_event(
                    logger,
                    logging.INFO,
                    "metadata_job_completed",
                    document_id=doc_id,
                    has_title=bool(result.title),
                    has_authors=bool(result.authors),
                )
            else:
                log_event(
                    logger, logging.INFO, "metadata_job_no_update", document_id=doc_id
                )

        asyncio.run(_run())
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "metadata_job_failed",
            document_id=doc_id,
            error=str(e),
        )


def start_job_worker(
    queue_repo: QueueRepository,
    stop_event: threading.Event | None = None,
    metadata_use_case: MetadataExtractionUseCase | None = None,
) -> threading.Thread:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.shared.config import (
        WORKER_BATCH_SIZE,
        WORKER_MAX_WORKERS,
        WORKER_POLL_INTERVAL,
    )

    interval = WORKER_POLL_INTERVAL
    batch_size = WORKER_BATCH_SIZE
    max_workers = WORKER_MAX_WORKERS
    _stop = stop_event or threading.Event()

    def _safe_complete(job_id: str) -> None:
        try:
            queue_repo.complete(job_id)
        except Exception:
            logger.warning(
                "job_queue_complete_failed id=%s (pool may be closed)", job_id
            )

    def _safe_fail(job_id: str, error: str) -> None:
        try:
            queue_repo.fail(job_id, error)
        except Exception:
            logger.warning("job_queue_fail_failed id=%s (pool may be closed)", job_id)

    def process_job(job: dict) -> None:
        job_type = job["job_type"]
        handler = _HANDLERS.get(job_type)
        if not handler:
            logger.warning("Unknown job type: %s", job_type)
            _safe_complete(job["id"])
            return

        try:
            payload = (
                json.loads(job["payload"])
                if isinstance(job["payload"], str)
                else job["payload"]
            )
            logger.info("Processing job %s: %s", job["id"], job_type)
            handler(payload, metadata_use_case)
            _safe_complete(job["id"])
            logger.info("Job completed: %s", job["id"])
        except Exception as e:
            error_msg = str(e)
            logger.error("Job failed %s: %s", job["id"], error_msg)
            _safe_fail(job["id"], error_msg)

    def tick() -> None:
        try:
            jobs = queue_repo.acquire_pending(limit=batch_size)
            if not jobs:
                return

            if max_workers == 1:
                for job in jobs:
                    process_job(job)
                return

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_job, job): job for job in jobs}
                for future in as_completed(futures):
                    future.result()
        except Exception as e:
            logger.error("Worker tick error: %s", e)

    def loop() -> None:
        tick()
        while not _stop.wait(timeout=interval):
            tick()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    log_event(
        logger,
        logging.INFO,
        "job_worker_started",
        poll_interval_seconds=interval,
        batch_size=batch_size,
        max_workers=max_workers,
    )
    return thread

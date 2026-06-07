from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Protocol

from src.infrastructure.persistence.queue_repository import QueueRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger(__name__)


class MetadataExtractor(Protocol):
    def execute(self, text: str) -> dict:
        pass


JobHandler = Callable[[dict, MetadataExtractor | None], None]

_HANDLERS: dict[str, JobHandler] = {}


@dataclass
class JobWorkerHandle:
    thread: threading.Thread
    stop_event: threading.Event
    _active_job_ids: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_active(self, job_id: str) -> None:
        with self._lock:
            self._active_job_ids.add(job_id)

    def remove_active(self, job_id: str) -> None:
        with self._lock:
            self._active_job_ids.discard(job_id)

    def active_job_ids(self) -> list[str]:
        with self._lock:
            return list(self._active_job_ids)

    def stop(self, timeout_seconds: int) -> bool:
        self.stop_event.set()
        self.thread.join(timeout=timeout_seconds)
        return not self.thread.is_alive()


def _register_handler(job_type: str):
    def decorator(fn):
        _HANDLERS[job_type] = fn
        return fn

    return decorator


@_register_handler("document.extract_metadata")
def _handle_extract_metadata(
    payload: dict, metadata_extractor: MetadataExtractor | None
) -> None:
    """Re-extract title/authors from a PDF document."""
    import asyncio

    doc_id = payload["document_id"]
    log_event(
        logger,
        logging.INFO,
        "metadata_job_started",
        document_id=doc_id,
    )

    async def _run():
        from src.infrastructure.persistence.postgres_document_repo import (
            PostgresDocumentRepository,
        )
        from src.shared.config import DATA_DIR

        if metadata_extractor is None:
            log_event(
                logger,
                logging.WARNING,
                "metadata_job_aborted",
                reason="extractor_not_available",
                document_id=doc_id,
            )
            return

        db = PostgresDocumentRepository()
        await db.initialize()
        try:
            doc = await db.get(doc_id)
            if not doc or doc.file_type != "pdf":
                return

            filepath = DATA_DIR / doc.directory / f"{doc.id}.{doc.file_type}"
            if not filepath.exists():
                return

            import fitz

            pdf_doc = None
            try:
                pdf_doc = fitz.open(str(filepath))
                pages = min(3, len(pdf_doc))
                texts = []
                for i in range(pages):
                    text = pdf_doc[i].get_text()
                    if text:
                        texts.append(text)
                first_page = "\n".join(texts)
            finally:
                if pdf_doc is not None:
                    pdf_doc.close()

            if not first_page.strip():
                return

            result = metadata_extractor.execute(first_page)
            ext_title = result.get("title", "").strip()
            ext_authors = result.get("authors", "").strip()

            if ext_title or ext_authors:
                from src.domain.models.document import DocumentUpdate

                await db.update(
                    doc_id,
                    DocumentUpdate(
                        title=ext_title or doc.title or None,
                        authors=ext_authors or doc.authors or None,
                    ),
                )
            log_event(
                logger,
                logging.INFO,
                "metadata_job_completed",
                document_id=doc_id,
                has_title=bool(ext_title),
                has_authors=bool(ext_authors),
            )
        finally:
            await db.close()

    asyncio.run(_run())


def start_job_worker(
    queue_repo: QueueRepository,
    stop_event: threading.Event | None = None,
    metadata_extractor: MetadataExtractor | None = None,
) -> JobWorkerHandle:
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
    worker_handle: JobWorkerHandle | None = None

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
        job_id = job["id"]
        handler = _HANDLERS.get(job_type)
        if not handler:
            logger.warning("Unknown job type: %s", job_type)
            _safe_complete(job_id)
            return

        assert worker_handle is not None
        worker_handle.add_active(job_id)
        try:
            payload = (
                json.loads(job["payload"])
                if isinstance(job["payload"], str)
                else job["payload"]
            )
            logger.info("Processing job %s: %s", job_id, job_type)
            handler(payload, metadata_extractor)
            _safe_complete(job_id)
            logger.info("Job completed: %s", job_id)
        except Exception as e:
            error_msg = str(e)
            logger.error("Job failed %s: %s", job_id, error_msg)
            _safe_fail(job_id, error_msg)
        finally:
            worker_handle.remove_active(job_id)

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
    worker_handle = JobWorkerHandle(thread=thread, stop_event=_stop)
    thread.start()
    log_event(
        logger,
        logging.INFO,
        "job_worker_started",
        poll_interval_seconds=interval,
        batch_size=batch_size,
        max_workers=max_workers,
    )
    return worker_handle

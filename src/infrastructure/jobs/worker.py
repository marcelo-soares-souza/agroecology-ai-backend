from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from src.infrastructure.persistence.queue_repository import QueueRepository

logger = logging.getLogger(__name__)

_HANDLERS: dict[str, Callable] = {}


def _register_handler(job_type: str):
    def decorator(fn):
        _HANDLERS[job_type] = fn
        return fn

    return decorator


@_register_handler("document.extract_metadata")
def _handle_extract_metadata(payload: dict) -> None:
    """Re-extract title/authors from a PDF document."""
    import asyncio

    doc_id = payload["document_id"]

    async def _run():
        from src.infrastructure.persistence.postgres_document_repo import (
            PostgresDocumentRepository,
        )
        from src.adapters.rest.dependencies import get_extract_metadata
        from src.shared.config import DATA_DIR

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

            pdf = fitz.open(str(filepath))
            pages = min(3, len(pdf))
            texts = [
                pdf[i].get_text()
                for i in range(pages)
                if pdf[i].get_text()
                if hasattr(pdf[i], "get_text")
            ]
            first_page = "\n".join(texts)
            pdf.close()

            if not first_page.strip():
                return

            extractor = get_extract_metadata()
            result = extractor.execute(first_page)
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
        finally:
            await db.close()

    asyncio.run(_run())


def start_job_worker(queue_repo: QueueRepository) -> threading.Thread:
    interval = 10  # seconds

    def tick():
        try:
            jobs = queue_repo.acquire_pending(limit=5)
            for job in jobs:
                job_type = job["job_type"]
                handler = _HANDLERS.get(job_type)
                if not handler:
                    logger.warning("Unknown job type: %s", job_type)
                    queue_repo.complete(job["id"])
                    continue

                try:
                    payload = (
                        json.loads(job["payload"])
                        if isinstance(job["payload"], str)
                        else job["payload"]
                    )
                    logger.info("Processing job %s: %s", job["id"], job_type)
                    handler(payload)
                    queue_repo.complete(job["id"])
                    logger.info("Job completed: %s", job["id"])
                except Exception as e:
                    error_msg = str(e)
                    logger.error("Job failed %s: %s", job["id"], error_msg)
                    queue_repo.fail(job["id"], error_msg)
        except Exception as e:
            logger.error("Worker tick error: %s", e)

    def loop():
        tick()
        while True:
            time.sleep(interval)
            tick()

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    logger.info("Job worker started (polling every %ds)", interval)
    return thread

from __future__ import annotations

import asyncio
import logging

from src.application.ingest_documents import IngestDocuments
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.bootstrap")


class IngestionTaskService:
    def __init__(self, ingest_documents: IngestDocuments) -> None:
        self._ingest_documents = ingest_documents

    def start(self, force: bool = False) -> str:
        if self._ingest_documents.status == "processing":
            log_event(logger, logging.WARNING, "ingest_start_rejected", force=force)
            return "already_running"

        self._ingest_documents.status = "processing"
        self._ingest_documents.error = None

        async def _run() -> None:
            try:
                await self._ingest_documents.execute(force=force)
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "ingest_background_failed",
                    error=str(exc),
                )

        asyncio.create_task(_run())
        log_event(logger, logging.INFO, "ingest_start_accepted", force=force)
        return "processing"

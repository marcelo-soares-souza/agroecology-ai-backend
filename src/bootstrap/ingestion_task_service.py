from __future__ import annotations

import logging
from collections.abc import Callable

from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.job_queue_port import JobQueuePort
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.bootstrap")


class IngestionTaskService:
    def __init__(
        self,
        ingestion_repo: IngestionRepository,
        queue: Callable[[], JobQueuePort],
    ) -> None:
        self._ingestion_repo = ingestion_repo
        self._get_queue = queue

    async def enqueue(self, force: bool = False) -> str | None:
        if await self._ingestion_repo.has_active_run():
            log_event(logger, logging.WARNING, "ingest_enqueue_rejected", force=force)
            return None

        run = await self._ingestion_repo.create_run(force=force)
        job_id = self._get_queue().enqueue(
            "documents.ingest",
            {"run_id": run.id, "force": force},
            max_retries=1,
        )
        await self._ingestion_repo.set_job_id(run.id, job_id)
        log_event(
            logger,
            logging.INFO,
            "ingest_enqueued",
            run_id=run.id,
            job_id=job_id,
            force=force,
        )
        return run.id

from __future__ import annotations

import logging
from collections.abc import Callable

from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)
from src.domain.ports.job_queue_port import JobQueuePort
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.academic_metadata")


class EnqueueAcademicMetadataExtraction:
    def __init__(
        self,
        run_repo: AcademicMetadataRunRepository,
        queue: Callable[[], JobQueuePort],
        default_delay_seconds: int,
        min_delay_seconds: int,
    ) -> None:
        self._run_repo = run_repo
        self._get_queue = queue
        self._default_delay_seconds = default_delay_seconds
        self._min_delay_seconds = min_delay_seconds

    async def execute(
        self,
        delay_seconds: int | None = None,
        force: bool = False,
        document_ids: list[str] | None = None,
    ) -> AcademicMetadataRun | None:
        delay = delay_seconds or self._default_delay_seconds
        if delay < self._min_delay_seconds:
            raise ValueError(
                f"Delay must be at least {self._min_delay_seconds} seconds"
            )

        if await self._run_repo.has_active_run():
            log_event(logger, logging.WARNING, "academic_metadata_enqueue_rejected")
            return None

        run = await self._run_repo.create_run(delay)
        job_id = self._get_queue().enqueue(
            "documents.extract_academic_metadata",
            {
                "run_id": run.id,
                "delay_seconds": delay,
                "force": force,
                "document_ids": document_ids or [],
            },
            max_retries=1,
        )
        updated = await self._run_repo.set_job_id(run.id, job_id)
        log_event(
            logger,
            logging.INFO,
            "academic_metadata_enqueued",
            run_id=run.id,
            job_id=job_id,
            delay_seconds=delay,
            force=force,
            document_count=len(document_ids or []),
        )
        return updated or run

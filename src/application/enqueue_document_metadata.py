from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.domain.ports.job_queue_port import JobQueuePort


@dataclass
class EnqueueMetadataResult:
    job_id: str


class EnqueueDocumentMetadata:
    def __init__(self, queue: Callable[[], JobQueuePort]) -> None:
        self._get_queue = queue

    def execute(self, document_id: str) -> EnqueueMetadataResult:
        job_id = self._get_queue().enqueue(
            "document.extract_metadata",
            {"document_id": document_id},
        )
        return EnqueueMetadataResult(job_id=job_id)

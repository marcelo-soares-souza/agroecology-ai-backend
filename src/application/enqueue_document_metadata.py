from __future__ import annotations

from src.domain.ports.job_queue_port import JobQueuePort


class EnqueueDocumentMetadata:
    def __init__(self, queue: JobQueuePort) -> None:
        self._queue = queue

    def execute(self, document_id: str) -> str:
        return self._queue.enqueue(
            "document.extract_metadata",
            {"document_id": document_id},
        )

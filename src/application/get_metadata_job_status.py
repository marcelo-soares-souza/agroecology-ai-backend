from __future__ import annotations

from src.domain.dto.document_result import MetadataExtractionQueueStatus
from src.domain.ports.job_queue_port import JobQueuePort


class GetMetadataJobStatus:
    def __init__(self, queue: JobQueuePort) -> None:
        self._queue = queue

    def execute(self) -> MetadataExtractionQueueStatus:
        counts = self._queue.count_by_status("document.extract_metadata")
        pending = counts.get("pending", 0)
        running = counts.get("running", 0)
        return MetadataExtractionQueueStatus(
            pending=pending,
            running=running,
            active=pending + running,
        )

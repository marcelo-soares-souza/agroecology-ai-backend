from __future__ import annotations

from collections.abc import Callable

from src.domain.dto.document_result import MetadataExtractionQueueStatus
from src.domain.ports.job_queue_port import JobQueuePort


class GetMetadataJobStatus:
    def __init__(self, queue: Callable[[], JobQueuePort]) -> None:
        self._get_queue = queue

    def execute(self) -> MetadataExtractionQueueStatus:
        counts = self._get_queue().count_by_status("document.extract_metadata")
        pending = counts.get("pending", 0)
        running = counts.get("running", 0)
        return MetadataExtractionQueueStatus(
            pending=pending,
            running=running,
            active=pending + running,
        )

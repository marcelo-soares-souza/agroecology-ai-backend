from __future__ import annotations

from collections.abc import Callable

from src.domain.dto.document_result import PendingMetadataEnqueueResult
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.job_queue_port import JobQueuePort


class EnqueuePendingMetadata:
    def __init__(
        self,
        repo: DocumentRepository,
        queue: Callable[[], JobQueuePort],
    ) -> None:
        self._repo = repo
        self._get_queue = queue

    async def execute(self) -> PendingMetadataEnqueueResult:
        docs = await self._repo.list_all()
        count = 0
        for doc in docs:
            if doc.file_type != "pdf":
                continue
            if doc.title and doc.title.strip() and doc.authors and doc.authors.strip():
                continue
            self._get_queue().enqueue(
                "document.extract_metadata",
                {"document_id": doc.id},
            )
            count += 1

        return PendingMetadataEnqueueResult(enqueued=count)

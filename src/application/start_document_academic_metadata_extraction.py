from __future__ import annotations

from src.application.enqueue_academic_metadata_extraction import (
    EnqueueAcademicMetadataExtraction,
)
from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.document_academic_metadata_attempt_repository import (
    DocumentAcademicMetadataAttemptRepository,
)
from src.domain.ports.document_repository import DocumentRepository


class StartDocumentAcademicMetadataExtraction:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        enqueue_extraction: EnqueueAcademicMetadataExtraction,
        attempt_repo: DocumentAcademicMetadataAttemptRepository | None = None,
    ) -> None:
        self._doc_repo = doc_repo
        self._enqueue_extraction = enqueue_extraction
        self._attempt_repo = attempt_repo

    async def execute(
        self,
        doc_id: str,
        delay_seconds: int | None = None,
        force: bool = True,
        batch_missing: bool = False,
    ) -> AcademicMetadataRun | None:
        doc = await self._doc_repo.get(doc_id)
        if not doc:
            raise LookupError("Document not found")
        if not (doc.title and doc.title.strip()) or not (
            doc.authors and doc.authors.strip()
        ):
            raise ValueError(
                "Title and authors are required for academic metadata extraction"
            )
        document_ids: list[str] | None = [doc_id]
        if batch_missing and not force:
            document_ids = None
            if (
                self._attempt_repo is not None
                and await self._attempt_repo.count_pending() <= 0
            ):
                raise ValueError(
                    "No eligible documents pending academic metadata extraction"
                )
        return await self._enqueue_extraction.execute(
            delay_seconds=delay_seconds,
            force=force,
            document_ids=document_ids,
        )

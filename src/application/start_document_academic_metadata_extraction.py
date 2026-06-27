from __future__ import annotations

from src.application.enqueue_academic_metadata_extraction import (
    EnqueueAcademicMetadataExtraction,
)
from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.document_repository import DocumentRepository


class StartDocumentAcademicMetadataExtraction:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        enqueue_extraction: EnqueueAcademicMetadataExtraction,
    ) -> None:
        self._doc_repo = doc_repo
        self._enqueue_extraction = enqueue_extraction

    async def execute(
        self,
        doc_id: str,
        delay_seconds: int | None = None,
        force: bool = True,
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
        return await self._enqueue_extraction.execute(
            delay_seconds=delay_seconds,
            force=force,
            document_ids=[doc_id],
        )


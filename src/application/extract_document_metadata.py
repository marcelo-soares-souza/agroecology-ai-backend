from __future__ import annotations

from src.application.extract_metadata import ExtractMetadata
from src.domain.dto.document_result import MetadataExtractionResult
from src.domain.models.document import DocumentUpdate
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.pdf_text_extractor_port import PdfTextExtractorPort
from src.shared.config import FILE_TYPE_TO_EXT


class ExtractDocumentMetadata:
    def __init__(
        self,
        repo: DocumentRepository,
        storage: FileStoragePort,
        pdf_text_extractor: PdfTextExtractorPort,
        metadata_extractor: ExtractMetadata,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._pdf_text_extractor = pdf_text_extractor
        self._metadata_extractor = metadata_extractor

    async def execute(self, doc_id: str) -> MetadataExtractionResult | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None

        if doc.file_type != "pdf":
            return None

        ext = FILE_TYPE_TO_EXT.get(doc.file_type)
        if not ext:
            return None

        content = await self._storage.read(doc.directory, doc.id, ext)
        first_page_text = self._pdf_text_extractor.extract_first_pages_text(content)
        if not first_page_text:
            return None

        result = self._metadata_extractor.execute(first_page_text)
        ext_title = result.title.strip()
        ext_authors = result.authors.strip()

        if not ext_title and not ext_authors:
            return None

        updated = await self._repo.update(
            doc_id,
            DocumentUpdate(
                title=ext_title or doc.title or None,
                authors=ext_authors or doc.authors or None,
            ),
        )
        if not updated:
            return None

        return MetadataExtractionResult(
            id=updated.id,
            title=updated.title,
            authors=updated.authors,
            filename=updated.filename,
            file_type=updated.file_type,
        )

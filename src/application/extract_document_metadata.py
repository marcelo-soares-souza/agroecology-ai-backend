from __future__ import annotations

import logging

from src.application.config import DocumentStorageConfig
from src.application.extract_metadata import ExtractMetadata
from src.domain.dto.document_result import MetadataExtractionResult
from src.domain.models.document import DocumentUpdate
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.pdf_text_extractor_port import PdfTextExtractorPort
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.metadata")

_UNKNOWN_AUTHORS = "Unknown"


class ExtractDocumentMetadata:
    def __init__(
        self,
        repo: DocumentRepository,
        storage: FileStoragePort,
        pdf_text_extractor: PdfTextExtractorPort,
        metadata_extractor: ExtractMetadata,
        config: DocumentStorageConfig,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._pdf_text_extractor = pdf_text_extractor
        self._metadata_extractor = metadata_extractor
        self._config = config

    async def execute(self, doc_id: str) -> MetadataExtractionResult | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None

        if doc.file_type != "pdf":
            return None

        ext = self._config.file_type_to_ext.get(doc.file_type)
        if not ext:
            return None

        content = await self._storage.read(doc.directory, doc.id, ext)

        first_page_text = self._pdf_text_extractor.extract_first_pages_text(content)
        result = None
        if first_page_text:
            result = self._metadata_extractor.execute(first_page_text)

        ext_title = result.title.strip() if result else ""
        ext_authors = result.authors.strip() if result else ""

        if not ext_authors:
            pdf_metadata = self._pdf_text_extractor.extract_pdf_metadata(content)
            ext_authors = (pdf_metadata.get("author") or "").strip()
            if ext_authors:
                log_event(
                    logger,
                    logging.INFO,
                    "metadata_authors_pdf_metadata_used",
                    document_id=doc_id,
                )

        if not ext_authors:
            ext_authors = _UNKNOWN_AUTHORS
            log_event(
                logger,
                logging.INFO,
                "metadata_authors_defaulted_unknown",
                document_id=doc_id,
            )

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

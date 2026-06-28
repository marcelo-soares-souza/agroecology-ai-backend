from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from src.domain.models.document import Document
from src.domain.ports.document_loader_port import DocumentLoaderPort, DocumentSource
from src.domain.ports.document_parser_port import DocumentParserPort
from src.infrastructure.parsers.markdown_parser import MarkdownDocumentParser
from src.infrastructure.parsers.pymupdf_parser import PyMuPdfDocumentParser
from src.infrastructure.parsers.text_parser import TextDocumentParser
from src.shared.config import DATA_DIR

logger = logging.getLogger("agroecology.ingestion")


class LocalDocumentLoader(DocumentLoaderPort):
    def __init__(self, file_type_to_ext: Mapping[str, str]) -> None:
        self._file_type_to_ext = file_type_to_ext
        self._pdf_parser = PyMuPdfDocumentParser()
        self._md_parser = MarkdownDocumentParser()
        self._txt_parser = TextDocumentParser()

    async def load(self, documents: Sequence[Document]) -> list[DocumentSource]:
        sources: list[DocumentSource] = []

        for document in documents:
            ext = self._file_type_to_ext.get(document.file_type)
            parser = self._parser_for_type(document.file_type)
            if not ext or parser is None:
                logger.warning(
                    "document_ingestion_skipped document_id=%s file_type=%s "
                    "reason=unsupported_file_type",
                    document.id,
                    document.file_type,
                )
                continue

            filepath = DATA_DIR / document.directory / f"{document.id}{ext}"
            if not filepath.exists():
                logger.warning(
                    "document_ingestion_skipped document_id=%s filename=%s "
                    "reason=file_missing path=%s",
                    document.id,
                    document.filename,
                    filepath,
                )
                continue

            try:
                rel = str(filepath.relative_to(DATA_DIR))
                parsed = parser.parse(filepath.read_bytes(), document.id, rel)
                sources.append(
                    DocumentSource(
                        source_path=rel,
                        doc_id=document.id,
                        file_type=document.file_type,
                        parsed=parsed,
                    )
                )
            except Exception as e:
                logger.warning(
                    "document_parse_failed document_id=%s filename=%s "
                    "file_type=%s error=%s",
                    document.id,
                    document.filename,
                    document.file_type,
                    e,
                )

        return sources

    def _parser_for_type(self, file_type: str) -> DocumentParserPort | None:
        if file_type == "pdf":
            return self._pdf_parser
        if file_type == "md":
            return self._md_parser
        if file_type == "txt":
            return self._txt_parser
        return None

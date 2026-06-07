from __future__ import annotations

import logging

from src.domain.ports.document_loader_port import DocumentLoaderPort, DocumentSource
from src.infrastructure.parsers.markdown_parser import MarkdownDocumentParser
from src.infrastructure.parsers.pymupdf_parser import PyMuPdfDocumentParser
from src.infrastructure.parsers.text_parser import TextDocumentParser
from src.shared.config import DATA_DIR, DATA_DIR_MARKDOWN, DATA_DIR_PDFS, DATA_DIR_WEB

logger = logging.getLogger("agroecology.ingestion")


class LocalDocumentLoader(DocumentLoaderPort):
    def __init__(self) -> None:
        self._pdf_parser = PyMuPdfDocumentParser()
        self._md_parser = MarkdownDocumentParser()
        self._txt_parser = TextDocumentParser()

    async def load_all(self) -> list[DocumentSource]:
        sources: list[DocumentSource] = []

        for fp in DATA_DIR_PDFS.glob("*.pdf"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = self._pdf_parser.parse(fp.read_bytes(), doc_id, rel)
                sources.append(
                    DocumentSource(
                        source_path=rel,
                        doc_id=doc_id,
                        file_type="pdf",
                        parsed=parsed,
                    )
                )
            except Exception as e:
                logger.warning("pdf_parse_failed file=%s error=%s", fp.name, e)

        for fp in DATA_DIR_MARKDOWN.glob("*.md"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = self._md_parser.parse(fp.read_bytes(), doc_id, rel)
                sources.append(
                    DocumentSource(
                        source_path=rel,
                        doc_id=doc_id,
                        file_type="md",
                        parsed=parsed,
                    )
                )
            except Exception as e:
                logger.warning("md_parse_failed file=%s error=%s", fp.name, e)

        for fp in DATA_DIR_WEB.glob("*.txt"):
            try:
                rel = str(fp.relative_to(DATA_DIR))
                doc_id = fp.stem
                parsed = self._txt_parser.parse(fp.read_bytes(), doc_id, rel)
                sources.append(
                    DocumentSource(
                        source_path=rel,
                        doc_id=doc_id,
                        file_type="txt",
                        parsed=parsed,
                    )
                )
            except Exception as e:
                logger.warning("txt_parse_failed file=%s error=%s", fp.name, e)

        return sources

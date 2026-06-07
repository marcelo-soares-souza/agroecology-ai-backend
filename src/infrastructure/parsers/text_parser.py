from __future__ import annotations

import logging

from src.domain.models.parsed_document import BlockType, ParsedBlock, ParsedDocument
from src.domain.ports.document_parser_port import DocumentParserPort

logger = logging.getLogger(__name__)


class TextDocumentParser(DocumentParserPort):
    def parse(self, content: bytes, document_id: str, source: str) -> ParsedDocument:
        text = content.decode("utf-8")
        doc = ParsedDocument(
            document_id=document_id,
            source=source,
            file_type="txt",
        )

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        blocks: list[ParsedBlock] = []

        # First non-empty paragraph is likely the title
        if paragraphs:
            doc.title = paragraphs[0][:200]

        for i, para in enumerate(paragraphs):
            block_type = BlockType.TITLE if i == 0 else BlockType.PARAGRAPH
            blocks.append(
                ParsedBlock(
                    document_id=document_id,
                    source=source,
                    page_number=1,
                    block_type=block_type,
                    section_title=None,
                    text=para,
                    order=i,
                )
            )

        doc.blocks = blocks
        logger.info(
            "txt_parsed document_id=%s blocks=%d",
            document_id,
            len(doc.blocks),
        )
        return doc

from __future__ import annotations

import logging
import re
from pathlib import Path

from src.domain.models.parsed_document import BlockType, ParsedBlock, ParsedDocument
from src.domain.ports.document_parser_port import DocumentParserPort

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
_SECTION_DELIM = re.compile(r"\n(?=#{1,6}\s)")


class MarkdownDocumentParser(DocumentParserPort):
    def parse(self, filepath: Path, document_id: str, source: str) -> ParsedDocument:
        text = filepath.read_text(encoding="utf-8")
        doc = ParsedDocument(
            document_id=document_id,
            source=source,
            file_type="md",
        )

        parts = _SECTION_DELIM.split(text)
        blocks: list[ParsedBlock] = []
        current_section: str | None = None

        for part in parts:
            lines = part.strip().split("\n", 1)
            heading_match = _HEADING_RE.match(lines[0]) if lines else None

            if heading_match:
                heading_text = heading_match.group(2).strip()
                current_section = heading_text

                blocks.append(
                    ParsedBlock(
                        document_id=document_id,
                        source=source,
                        page_number=1,
                        block_type=BlockType.SECTION_HEADING,
                        section_title=current_section,
                        text=heading_text,
                        order=len(blocks),
                    )
                )

                if len(lines) > 1 and lines[1].strip():
                    body = lines[1].strip()
                else:
                    continue
            else:
                body = part.strip()
                if not body:
                    continue

            clean = body.strip().lower()
            if clean in ("abstract", "resumo"):
                blocks[-1].block_type = BlockType.ABSTRACT
                continue
            if clean in (
                "references",
                "referências",
                "referencias",
                "bibliography",
                "bibliografia",
            ):
                blocks[-1].block_type = BlockType.REFERENCE
                continue

            blocks.append(
                ParsedBlock(
                    document_id=document_id,
                    source=source,
                    page_number=1,
                    block_type=BlockType.PARAGRAPH,
                    section_title=current_section,
                    text=body,
                    order=len(blocks),
                )
            )

        # Detect title from first heading
        for b in blocks:
            if b.block_type == BlockType.SECTION_HEADING:
                doc.title = b.text
                break

        doc.blocks = blocks
        logger.info(
            "md_parsed document_id=%s blocks=%d sections=%d",
            document_id,
            len(doc.blocks),
            len(doc.sections),
        )
        return doc

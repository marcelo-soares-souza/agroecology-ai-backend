from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
    """Enumeration of semantic block types found in parsed documents."""

    TITLE = "title"
    ABSTRACT = "abstract"
    SECTION_HEADING = "section_heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE_CAPTION = "figure_caption"
    REFERENCE = "reference"
    FOOTNOTE = "footnote"
    UNKNOWN = "unknown"


@dataclass
class ParsedBlock:
    """A single semantic block extracted from a document.

    Attributes:
        document_id: The parent document's identifier.
        source: Source path of the document.
        page_number: The page number this block appears on.
        block_type: The semantic type of the block.
        section_title: The section heading this block belongs to.
        text: The block's text content.
        order: Sort order of this block within the document.
        font_name: The font used for this block.
        font_size: The font size in points.
        is_bold: Whether the text is bold.
        bbox: Bounding box coordinates (x0, y0, x1, y1).
    """

    document_id: str
    source: str
    page_number: int
    block_type: BlockType
    section_title: str | None
    text: str
    order: int

    font_name: str | None = None
    font_size: float | None = None
    is_bold: bool = False
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class ParsedDocument:
    """A fully parsed document with structured blocks and metadata.

    Attributes:
        document_id: The document's unique identifier.
        source: The source path or identifier.
        file_type: The file type (e.g., 'pdf', 'md').
        blocks: The ordered list of parsed blocks.
        title: The document's title, if detected.
        authors: The document's authors, if detected.
        year: The publication year, if detected.
        doi: The DOI, if detected.
        journal: The journal name, if detected.
        abstract: The abstract text, if detected.
        keywords: Extracted keywords.
        language: The document's language code.
        total_pages: Total number of pages.
    """

    document_id: str
    source: str
    file_type: str
    blocks: list[ParsedBlock] = field(default_factory=list)

    title: str | None = None
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    journal: str | None = None
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)
    language: str | None = None
    total_pages: int = 0

    @property
    def full_text(self) -> str:
        return "\n\n".join(b.text for b in sorted(self.blocks, key=lambda b: b.order))

    @property
    def sections(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for b in self.blocks:
            if b.section_title and b.section_title not in seen:
                seen.add(b.section_title)
                result.append(b.section_title)
        return result

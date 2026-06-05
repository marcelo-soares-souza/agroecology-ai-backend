from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
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

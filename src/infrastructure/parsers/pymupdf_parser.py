from __future__ import annotations

import logging
import re

from src.domain.models.parsed_document import BlockType, ParsedBlock, ParsedDocument
from src.domain.ports.document_parser_port import DocumentParserPort

logger = logging.getLogger(__name__)

_ACADEMIC_SECTIONS = {
    "abstract": BlockType.ABSTRACT,
    "resumo": BlockType.ABSTRACT,
    "introduction": BlockType.SECTION_HEADING,
    "introdução": BlockType.SECTION_HEADING,
    "introducao": BlockType.SECTION_HEADING,
    "materials and methods": BlockType.SECTION_HEADING,
    "materiais e métodos": BlockType.SECTION_HEADING,
    "materiais e metodos": BlockType.SECTION_HEADING,
    "material and methods": BlockType.SECTION_HEADING,
    "methods": BlockType.SECTION_HEADING,
    "metodologia": BlockType.SECTION_HEADING,
    "results": BlockType.SECTION_HEADING,
    "resultados": BlockType.SECTION_HEADING,
    "discussion": BlockType.SECTION_HEADING,
    "discussão": BlockType.SECTION_HEADING,
    "discussao": BlockType.SECTION_HEADING,
    "conclusion": BlockType.SECTION_HEADING,
    "conclusão": BlockType.SECTION_HEADING,
    "conclusao": BlockType.SECTION_HEADING,
    "references": BlockType.REFERENCE,
    "referências": BlockType.REFERENCE,
    "referencias": BlockType.REFERENCE,
    "bibliography": BlockType.REFERENCE,
    "bibliografia": BlockType.REFERENCE,
}

_HEADING_PATTERNS = [
    re.compile(r"^\s*(\d+(?:\.\d+)*)\s+(.+)", re.IGNORECASE),
    re.compile(r"^\s*([IVXLCDM]+)\.\s+(.+)", re.IGNORECASE),
]

_DOI_PATTERN = re.compile(r"\b(10\.\d{4,}/[^\s]+)\b")
_YEAR_PATTERN = re.compile(r"\b(19[7-9]\d|20[0-2]\d)\b")
_JOURNAL_HINTS = [
    r"journal of",
    r"revista",
    r"proceedings",
    r"annals",
    r"boletim",
    r"acta",
    r"pesquisa",
]


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_heading(text: str, font_size: float, base_size: float, is_bold: bool) -> bool:
    clean = text.strip().rstrip(".")
    if not clean or len(clean) > 150:
        return False
    if font_size > base_size * 1.15 or is_bold:
        if len(clean.split()) <= 20:
            return True
    for pattern in _HEADING_PATTERNS:
        if pattern.match(clean):
            return True
    return False


def _detect_section(text: str) -> str | None:
    clean = _clean_text(text).lower().rstrip(".")
    if clean in _ACADEMIC_SECTIONS:
        return text.strip()
    for key in _ACADEMIC_SECTIONS:
        if clean.startswith(key) and len(clean) < len(key) + 30:
            return text.strip()
    return None


def _classify_block(
    text: str,
    font_size: float,
    base_size: float,
    is_bold: bool,
    current_section: str | None,
) -> BlockType:
    clean = _clean_text(text).lower().rstrip(".")

    if (
        current_section
        and _ACADEMIC_SECTIONS.get(current_section.lower().rstrip("."))
        == BlockType.REFERENCE
    ):
        return BlockType.REFERENCE

    if _is_heading(text, font_size, base_size, is_bold):
        section_name = _detect_section(text)
        if section_name:
            section_lower = section_name.lower().rstrip(".")
            return _ACADEMIC_SECTIONS.get(section_lower, BlockType.SECTION_HEADING)
        return BlockType.SECTION_HEADING

    if _ACADEMIC_SECTIONS.get(clean) == BlockType.ABSTRACT:
        return BlockType.ABSTRACT

    if clean.startswith("fig") or clean.startswith("figure"):
        return BlockType.FIGURE_CAPTION

    if clean.startswith("table") and len(clean) < 80:
        return BlockType.TABLE

    if len(clean) < 30 and (
        clean.startswith("*") or clean.startswith("†") or clean.startswith("‡")
    ):
        return BlockType.FOOTNOTE

    return BlockType.PARAGRAPH


def _extract_meta(text: str) -> dict:
    result: dict = {"year": None, "doi": None}
    doi_match = _DOI_PATTERN.search(text)
    if doi_match:
        result["doi"] = doi_match.group(1)
    year_matches = _YEAR_PATTERN.findall(text)
    if year_matches:
        years = [int(y) for y in year_matches if 1975 <= int(y) <= 2026]
        if years:
            result["year"] = max(years)
    return result


class PyMuPdfDocumentParser(DocumentParserPort):
    def parse(self, content: bytes, document_id: str, source: str) -> ParsedDocument:
        import fitz

        doc = ParsedDocument(
            document_id=document_id,
            source=source,
            file_type="pdf",
        )

        pdf = fitz.open(stream=content, filetype="pdf")
        doc.total_pages = len(pdf)
        raw_blocks: list[tuple[int, float, float, bool, tuple, str]] = []
        page_header_texts: dict[str, list[str]] = {}
        page_footer_texts: dict[str, list[str]] = {}

        try:
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                blocks = page.get_text("dict")["blocks"]
                page_base_font = self._compute_base_font_size(blocks)

                for block in blocks:
                    if block.get("type") != 0:
                        continue

                    block_text = ""
                    fonts: list[float] = []
                    bold_count = 0
                    total_spans = 0

                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span["text"]
                            fonts.append(span["size"])
                            total_spans += 1
                            if "Bold" in span.get("font", ""):
                                bold_count += 1

                    block_text = _clean_text(block_text)
                    if not block_text or len(block_text) < 2:
                        continue

                    avg_font = sum(fonts) / len(fonts) if fonts else page_base_font
                    is_bold = (
                        bold_count / total_spans > 0.5 if total_spans > 0 else False
                    )
                    bbox = tuple(block.get("bbox", ()))

                    # Collect header/footer candidates (top/bottom 8% of page)
                    page_height = page.rect.height
                    if bbox and len(bbox) == 4:
                        if bbox[1] < page_height * 0.08:
                            page_header_texts.setdefault(str(page_num), []).append(
                                block_text
                            )
                        if bbox[3] > page_height * 0.92:
                            page_footer_texts.setdefault(str(page_num), []).append(
                                block_text
                            )

                    raw_blocks.append(
                        (page_num, avg_font, page_base_font, is_bold, bbox, block_text)
                    )

            # Identify recurring headers/footers to filter out
            recurring = self._find_recurring(page_header_texts, page_footer_texts)

            current_section: str | None = None
            parsed_blocks: list[ParsedBlock] = []
            title_candidates: list[tuple[int, str, float]] = []

            for order, (
                page_num,
                font_size,
                block_base,
                is_bold,
                bbox,
                text,
            ) in enumerate(raw_blocks):
                if self._is_recurring(text, recurring):
                    continue

                block_type = _classify_block(
                    text, font_size, block_base, is_bold, current_section
                )
                section_name = _detect_section(text)

                if section_name:
                    current_section = section_name
                if block_type == BlockType.SECTION_HEADING and not section_name:
                    pass

                if (
                    order < 5
                    and block_type in (BlockType.PARAGRAPH, BlockType.TITLE)
                    and font_size >= block_base * 1.2
                ):
                    title_candidates.append((order, text, font_size))

                parsed_blocks.append(
                    ParsedBlock(
                        document_id=document_id,
                        source=source,
                        page_number=page_num + 1,
                        block_type=block_type,
                        section_title=current_section,
                        text=text,
                        order=len(parsed_blocks),
                        font_name=None,
                        font_size=font_size,
                        is_bold=is_bold,
                        bbox=bbox,
                    )
                )

            # Extract title from first large-text block
            if title_candidates:
                title_candidates.sort(key=lambda x: (-x[2], x[0]))
                doc.title = _clean_text(title_candidates[0][1])

            # Extract metadata from first pages
            first_text = " ".join(b.text for b in parsed_blocks if b.page_number <= 3)
            meta = _extract_meta(first_text)
            if meta["year"]:
                doc.year = meta["year"]
            if meta["doi"]:
                doc.doi = meta["doi"]

            # Detect abstract
            for b in parsed_blocks:
                if b.block_type == BlockType.ABSTRACT:
                    abstract_parts = []
                    for ab in parsed_blocks[b.order :]:
                        if ab.block_type in (
                            BlockType.SECTION_HEADING,
                            BlockType.REFERENCE,
                        ):
                            break
                        if ab.block_type == BlockType.PARAGRAPH:
                            abstract_parts.append(ab.text)
                    doc.abstract = " ".join(abstract_parts)
                    break

            doc.blocks = parsed_blocks

        finally:
            pdf.close()

        logger.info(
            "pdf_parsed document_id=%s pages=%d blocks=%d sections=%d title=%s",
            document_id,
            doc.total_pages,
            len(doc.blocks),
            len(doc.sections),
            doc.title or "(none)",
        )
        return doc

    @staticmethod
    def _compute_base_font_size(blocks: list[dict]) -> float:
        font_sizes: list[float] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["size"] > 5:
                        font_sizes.append(span["size"])
        if not font_sizes:
            return 12.0
        font_sizes.sort()
        return font_sizes[len(font_sizes) // 2]

    @staticmethod
    def _find_recurring(
        headers: dict[str, list[str]],
        footers: dict[str, list[str]],
    ) -> set[str]:
        recurring: set[str] = set()
        all_hf: list[list[str]] = list(headers.values()) + list(footers.values())
        if len(all_hf) < 3:
            return recurring

        for texts in all_hf:
            for t in texts:
                t = _clean_text(t)
                if len(t) < 3 or len(t) > 100:
                    continue
                count = sum(
                    1 for other in all_hf if any(_clean_text(o) == t for o in other)
                )
                if count >= 2:
                    recurring.add(t)
        return recurring

    @staticmethod
    def _is_recurring(text: str, recurring: set[str]) -> bool:
        return _clean_text(text) in recurring

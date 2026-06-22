from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.domain.models.parsed_document import BlockType, ParsedBlock

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c0-\u00da\u00c7])")
_SHORT_BODY_FRAGMENT_CHARS = 120
_CHARS_PER_TOKEN = 4
_EXCLUDED_BLOCK_TYPES = {
    BlockType.REFERENCE,
    BlockType.FOOTNOTE,
    BlockType.SECTION_HEADING,
    BlockType.TITLE,
}
_SELF_CONTAINED_BLOCKS = {
    BlockType.ABSTRACT,
    BlockType.TABLE,
    BlockType.FIGURE_CAPTION,
}
_REFERENCE_SECTION_RE = re.compile(
    r"\b(references?|refer[eê]ncias?|referencias|bibliograph(?:y|ie)|bibliografia)\b",
    re.IGNORECASE,
)
_EVIDENCE_SECTION_RE = re.compile(
    r"\b("
    r"abstract|resumo|resumen|"
    r"method|methods|metodologia|m[eé]todos?|materiais|materials|"
    r"results?|resultados?|discussion|discuss[aã]o|discusi[oó]n|"
    r"conclusions?|conclus[aã]o|conclusiones"
    r")\b",
    re.IGNORECASE,
)
_EDITORIAL_NOISE_PATTERNS = (
    re.compile(
        r"^(received|revised|accepted|published|submitted|available online)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^(recebido|revisado|aceito|aprovado|publicado)\b", re.IGNORECASE),
    re.compile(r"^(recibido|revisado|aceptado|publicado)\b", re.IGNORECASE),
    re.compile(r"\bcreative commons\b|\bcc[- ]?by\b", re.IGNORECASE),
    re.compile(r"\bopen access\b.*\blicen[cs]e\b", re.IGNORECASE),
    re.compile(r"^(copyright\b|©|\(c\))", re.IGNORECASE),
    re.compile(r"^correspond(ence|ing author)\b", re.IGNORECASE),
    re.compile(r"^e-?mail\b|^email\b", re.IGNORECASE),
    re.compile(r"^publisher'?s note\b", re.IGNORECASE),
    re.compile(r"^conflicts? of interest\b", re.IGNORECASE),
    re.compile(r"^funding\b", re.IGNORECASE),
    re.compile(r"^doi:\s*10\.\d{4,}/", re.IGNORECASE),
)
_AFFILIATION_RE = re.compile(
    r"^(\d+|[a-z])?\s*"
    r"(department|faculty|school|institute|university|universidade|instituto|"
    r"departamento|faculdade|laboratory|laboratorio|laborat[oó]rio)\b",
    re.IGNORECASE,
)
_BARE_CAPTION_RE = re.compile(r"^(fig(?:ure)?|figura|table|tabela|tabla)\s*\d+\.?$")
_NUMERIC_VALUE_RE = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class _BlockPart:
    text: str
    page_start: int
    page_end: int
    block_types: set[str]

    def merge(self, other: "_BlockPart") -> "_BlockPart":
        return _BlockPart(
            text=f"{self.text} {other.text}".strip(),
            page_start=min(self.page_start, other.page_start),
            page_end=max(self.page_end, other.page_end),
            block_types={*self.block_types, *other.block_types},
        )


@dataclass
class ChunkMetadata:
    """Metadata attached to each chunk produced by the chunking pipeline.

    Attributes:
        document_id: The parent document's unique identifier.
        section_title: The section heading this chunk belongs to.
        page_start: First page number covered by this chunk.
        page_end: Last page number covered by this chunk.
        chunk_index: Zero-based position of this chunk within the document.
        block_types: List of block type identifiers in this chunk.
        token_estimate: Estimated token count for the chunk text.
    """

    document_id: str
    section_title: str | None
    page_start: int
    page_end: int
    chunk_index: int
    block_types: list[str] = field(default_factory=list)
    token_estimate: int = 0


def estimate_tokens(text: str) -> int:
    """Roughly estimate the token count of a text.

    Args:
        text: The input text.

    Returns:
        Estimated token count (at least 1).
    """
    return max(1, len(text) // 4)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_reference_section(section_title: str | None) -> bool:
    return bool(section_title and _REFERENCE_SECTION_RE.search(section_title))


def _is_evidence_protected(block: ParsedBlock) -> bool:
    if block.block_type in _SELF_CONTAINED_BLOCKS:
        return True
    return bool(
        block.section_title and _EVIDENCE_SECTION_RE.search(block.section_title)
    )


def _is_editorial_noise(block: ParsedBlock) -> bool:
    text = _normalize_text(block.text)
    if not text or _is_evidence_protected(block):
        return False

    if "@" in text and len(text) < 220:
        return True

    if len(text) < 260 and _AFFILIATION_RE.search(text):
        return True

    return any(pattern.search(text) for pattern in _EDITORIAL_NOISE_PATTERNS)


def _is_informative_special_block(block: ParsedBlock) -> bool:
    text = _normalize_text(block.text)
    if not text:
        return False

    if block.block_type == BlockType.ABSTRACT:
        return len(text) >= 40

    if block.block_type == BlockType.FIGURE_CAPTION:
        return len(text) >= 40 and not _BARE_CAPTION_RE.match(text)

    if block.block_type == BlockType.TABLE:
        numeric_values = len(_NUMERIC_VALUE_RE.findall(text))
        return len(text) >= 120 or numeric_values >= 3

    return True


def _should_index_block(block: ParsedBlock) -> bool:
    if block.block_type in _EXCLUDED_BLOCK_TYPES:
        return False
    if _is_reference_section(block.section_title):
        return False
    if _is_editorial_noise(block):
        return False
    if block.block_type in _SELF_CONTAINED_BLOCKS:
        return _is_informative_special_block(block)
    return bool(_normalize_text(block.text))


def _to_part(block: ParsedBlock) -> _BlockPart:
    text = _normalize_text(block.text)
    return _BlockPart(
        text=text,
        page_start=block.page_number,
        page_end=block.page_number,
        block_types={block.block_type.value},
    )


def _can_merge_short_part(left: _BlockPart, right: _BlockPart) -> bool:
    return left.page_end == right.page_start


def _merge_short_body_parts(parts: list[_BlockPart]) -> list[_BlockPart]:
    merged: list[_BlockPart] = []
    index = 0

    while index < len(parts):
        part = parts[index]
        if len(part.text) >= _SHORT_BODY_FRAGMENT_CHARS:
            merged.append(part)
            index += 1
            continue

        next_part = parts[index + 1] if index + 1 < len(parts) else None
        if next_part and _can_merge_short_part(part, next_part):
            merged.append(part.merge(next_part))
            index += 2
            continue

        if merged and _can_merge_short_part(merged[-1], part):
            merged[-1] = merged[-1].merge(part)

        index += 1

    return merged


def _split_long_part(
    part: _BlockPart, chunk_size: int, overlap: int
) -> list[_BlockPart]:
    if (
        estimate_tokens(part.text) <= chunk_size
        or BlockType.TABLE.value in part.block_types
    ):
        return [part]

    split_texts = chunk_text(part.text, chunk_size=chunk_size, overlap=overlap)
    return [
        _BlockPart(
            text=text,
            page_start=part.page_start,
            page_end=part.page_end,
            block_types=set(part.block_types),
        )
        for text in split_texts
        if text.strip()
    ]


def _build_embedding_text(
    embedding_prefix: str,
    section_prefix: str,
    text: str,
) -> str:
    parts = [embedding_prefix, section_prefix, f"Passage: {text}"]
    return " ".join(part.strip() for part in parts if part.strip())


def _build_chunk(
    parts: list[_BlockPart],
    document_id: str,
    section_title: str | None,
    chunk_index: int,
    embedding_prefix: str,
    section_prefix: str,
) -> tuple[str, str, ChunkMetadata] | None:
    chunk_text = " ".join(part.text for part in parts).strip()
    if not chunk_text:
        return None

    block_types: set[str] = set()
    for part in parts:
        block_types.update(part.block_types)

    meta = ChunkMetadata(
        document_id=document_id,
        section_title=section_title,
        page_start=min(part.page_start for part in parts),
        page_end=max(part.page_end for part in parts),
        chunk_index=chunk_index,
        block_types=sorted(block_types),
        token_estimate=estimate_tokens(chunk_text),
    )
    embedding_text = _build_embedding_text(
        embedding_prefix=embedding_prefix,
        section_prefix=section_prefix,
        text=chunk_text,
    )
    return chunk_text, embedding_text, meta


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, respecting paragraph boundaries.

    Args:
        text: The input text.

    Returns:
        A list of sentence strings.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    sentences: list[str] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        parts = _SENTENCE_END.split(para)
        for part in parts:
            if "\n" in part:
                sentences.extend(
                    line.strip() for line in part.split("\n") if line.strip()
                )
            else:
                part = part.strip()
                if part:
                    sentences.append(part)

    return sentences


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Split plain text into overlapping chunks of roughly equal token size.

    Args:
        text: The input text.
        chunk_size: Target chunk size in tokens.
        overlap: Overlap between consecutive chunks in tokens.

    Returns:
        A list of chunk text strings.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunk_size_chars = chunk_size * _CHARS_PER_TOKEN
    overlap_chars = overlap * _CHARS_PER_TOKEN

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)

        if current_len + sent_len > chunk_size_chars and current:
            chunks.append(" ".join(current))

            overlap_parts: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) <= overlap_chars:
                    overlap_parts.insert(0, s)
                    overlap_len += len(s)
                else:
                    break

            current = overlap_parts
            current_len = overlap_len

        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))

    return chunks or [text]


def chunk_blocks(
    blocks: list[ParsedBlock],
    document_id: str,
    chunk_size: int,
    overlap: int,
    title: str | None = None,
    authors: str | None = None,
    year: int | None = None,
) -> list[tuple[str, str, ChunkMetadata]]:
    """Chunk ParsedBlock list into (text, embedding_text, metadata) tuples.

    Groups blocks by section, avoids mixing sections in the same chunk,
    and produces enriched embedding_text with document context.

    Args:
        blocks: The parsed blocks to chunk.
        document_id: The parent document's identifier.
        title: The document's title for embedding enrichment.
        authors: The document's authors for embedding enrichment.
        year: The publication year for embedding enrichment.
        chunk_size: Target chunk size in tokens.
        overlap: Overlap between consecutive chunks in tokens.

    Returns:
        A list of (chunk_text, embedding_text, ChunkMetadata) tuples.
    """

    if not blocks:
        return []

    # Group indexable evidence blocks by section.
    sections: dict[str | None, list[ParsedBlock]] = {}
    section_order: list[str | None] = []
    for b in blocks:
        if not _should_index_block(b):
            continue
        key = b.section_title
        if key not in sections:
            sections[key] = []
            section_order.append(key)
        sections[key].append(b)

    results: list[tuple[str, str, ChunkMetadata]] = []
    chunk_index = 0

    # Build embedding prefix with document context
    embedding_prefix_parts: list[str] = []
    if title:
        embedding_prefix_parts.append(f"Document title: {title}.")
    if authors:
        embedding_prefix_parts.append(f"Authors: {authors}.")
    if year:
        embedding_prefix_parts.append(f"Year: {year}.")
    embedding_prefix = " ".join(embedding_prefix_parts)

    for section_title in section_order:
        section_blocks = sections[section_title]
        section_prefix = f"Section: {section_title}. " if section_title else ""

        # Special blocks remain standalone, but long narrative blocks are split
        # by sentence so the reranked text can fit in the LLM context intact.
        for b in section_blocks:
            if b.block_type not in _SELF_CONTAINED_BLOCKS:
                continue

            for part in _split_long_part(_to_part(b), chunk_size, overlap):
                chunk = _build_chunk(
                    parts=[part],
                    document_id=document_id,
                    section_title=section_title,
                    chunk_index=chunk_index,
                    embedding_prefix=embedding_prefix,
                    section_prefix=section_prefix,
                )
                if chunk is None:
                    continue
                results.append(chunk)
                chunk_index += 1

        # Body paragraphs: chunk greedily within section
        body_blocks = [
            b for b in section_blocks if b.block_type not in _SELF_CONTAINED_BLOCKS
        ]
        if not body_blocks:
            continue

        body_parts: list[_BlockPart] = []
        for body_block in body_blocks:
            body_parts.append(_to_part(body_block))

        split_parts: list[_BlockPart] = []
        for part in _merge_short_body_parts(body_parts):
            split_parts.extend(_split_long_part(part, chunk_size, overlap))

        chunk_size_chars = chunk_size * _CHARS_PER_TOKEN
        overlap_chars = overlap * _CHARS_PER_TOKEN

        current: list[_BlockPart] = []
        current_len = 0

        for part in split_parts:
            if not part.text:
                continue

            if current_len + len(part.text) > chunk_size_chars and current:
                chunk = _build_chunk(
                    parts=current,
                    document_id=document_id,
                    section_title=section_title,
                    chunk_index=chunk_index,
                    embedding_prefix=embedding_prefix,
                    section_prefix=section_prefix,
                )
                if chunk is not None:
                    results.append(chunk)
                    chunk_index += 1

                # Overlap
                overlap_parts: list[_BlockPart] = []
                overlap_len = 0
                for s in reversed(current):
                    if overlap_len + len(s.text) <= overlap_chars:
                        overlap_parts.insert(0, s)
                        overlap_len += len(s.text)
                    else:
                        break

                current = overlap_parts
                current_len = overlap_len

            current.append(part)
            current_len += len(part.text)

        # Last chunk in section
        if current:
            chunk = _build_chunk(
                parts=current,
                document_id=document_id,
                section_title=section_title,
                chunk_index=chunk_index,
                embedding_prefix=embedding_prefix,
                section_prefix=section_prefix,
            )
            if chunk is not None:
                results.append(chunk)
                chunk_index += 1

    return results

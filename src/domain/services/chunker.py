import re
from dataclasses import dataclass, field

from src.domain.models.parsed_document import BlockType, ParsedBlock
from src.shared.config import CHUNK_OVERLAP, CHUNK_SIZE

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c0-\u00da\u00c7])")


@dataclass
class ChunkMetadata:
    document_id: str
    section_title: str | None
    page_start: int
    page_end: int
    chunk_index: int
    block_types: list[str] = field(default_factory=list)
    token_estimate: int = 0


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def split_sentences(text: str) -> list[str]:
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
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunk_size_chars = chunk_size * 4
    overlap_chars = overlap * 4

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
    title: str | None = None,
    authors: str | None = None,
    year: int | None = None,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[str, str, ChunkMetadata]]:
    """Chunk ParsedBlock list into (text, embedding_text, metadata) tuples.

    Groups blocks by section, avoids mixing sections in the same chunk,
    and produces enriched embedding_text with document context.
    """

    if not blocks:
        return []

    # Group blocks by section
    sections: dict[str | None, list[ParsedBlock]] = {}
    section_order: list[str | None] = []
    for b in blocks:
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

    SELF_CONTAINED_BLOCKS = {
        BlockType.ABSTRACT,
        BlockType.TABLE,
        BlockType.FIGURE_CAPTION,
    }

    for section_title in section_order:
        section_blocks = sections[section_title]
        section_prefix = f"Section: {section_title}. " if section_title else ""

        # Special blocks: each gets its own chunk
        for b in section_blocks:
            if b.block_type in SELF_CONTAINED_BLOCKS:
                block_text = b.text.strip()
                if not block_text:
                    continue
                embedding_text = (
                    f"{embedding_prefix} {section_prefix}Passage: {block_text}"
                )

                results.append(
                    (
                        block_text,
                        embedding_text,
                        ChunkMetadata(
                            document_id=document_id,
                            section_title=section_title,
                            page_start=b.page_number,
                            page_end=b.page_number,
                            chunk_index=chunk_index,
                            block_types=[b.block_type.value],
                            token_estimate=estimate_tokens(block_text),
                        ),
                    )
                )
                chunk_index += 1

        # Body paragraphs: chunk greedily within section
        body_blocks = [
            b for b in section_blocks if b.block_type not in SELF_CONTAINED_BLOCKS
        ]
        if not body_blocks:
            continue

        chunk_size_chars = chunk_size * 4
        overlap_chars = overlap * 4

        current: list[str] = []
        current_len = 0
        current_pages: list[int] = []
        current_block_types: set[str] = set()

        for b in body_blocks:
            text = b.text.strip()
            if not text:
                continue

            if current_len + len(text) > chunk_size_chars and current:
                chunk_text = " ".join(current)
                embedding_text = (
                    f"{embedding_prefix} {section_prefix}Passage: {chunk_text}"
                )

                meta = ChunkMetadata(
                    document_id=document_id,
                    section_title=section_title,
                    page_start=min(current_pages) if current_pages else 0,
                    page_end=max(current_pages) if current_pages else 0,
                    chunk_index=chunk_index,
                    block_types=sorted(current_block_types),
                    token_estimate=estimate_tokens(chunk_text),
                )
                results.append((chunk_text, embedding_text, meta))
                chunk_index += 1

                # Overlap
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
                current_pages = (
                    current_pages[-2:] if len(current_pages) >= 2 else current_pages
                )
                current_block_types = set()

            current.append(text)
            current_len += len(text)
            current_pages.append(b.page_number)
            current_block_types.add(b.block_type.value)

        # Last chunk in section
        if current:
            chunk_text = " ".join(current)
            embedding_text = f"{embedding_prefix} {section_prefix}Passage: {chunk_text}"
            meta = ChunkMetadata(
                document_id=document_id,
                section_title=section_title,
                page_start=min(current_pages) if current_pages else 0,
                page_end=max(current_pages) if current_pages else 0,
                chunk_index=chunk_index,
                block_types=sorted(current_block_types),
                token_estimate=estimate_tokens(chunk_text),
            )
            results.append((chunk_text, embedding_text, meta))
            chunk_index += 1

    return results

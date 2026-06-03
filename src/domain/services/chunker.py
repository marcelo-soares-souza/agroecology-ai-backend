import re

from src.shared.config import CHUNK_OVERLAP, CHUNK_SIZE

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u00c0-\u00da\u00c7])")


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

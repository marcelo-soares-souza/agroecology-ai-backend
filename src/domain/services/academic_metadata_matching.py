from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from src.domain.models.document_academic_metadata import AcademicMetadataCandidate


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_authors(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*;\s*|\s*,\s*|\s+\band\b\s+", value)
    return [part.strip() for part in parts if part.strip()]


def title_similarity(local_title: str | None, candidate_title: str | None) -> float:
    local = normalize_text(local_title)
    candidate = normalize_text(candidate_title)
    if not local or not candidate:
        return 0.0
    return SequenceMatcher(None, local, candidate).ratio()


def author_similarity(local_authors: list[str], candidate_authors: list[str]) -> float:
    if not local_authors or not candidate_authors:
        return 0.0

    available = set(range(len(candidate_authors)))
    matched_scores: list[float] = []

    for local_author in local_authors:
        best_index = None
        best_score = 0.0
        for index in available:
            score = author_name_similarity(local_author, candidate_authors[index])
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is not None:
            available.remove(best_index)
        matched_scores.append(best_score)

    return sum(matched_scores) / len(local_authors)


def author_validation_passed(
    local_authors: list[str],
    candidate: AcademicMetadataCandidate,
    threshold: float,
) -> bool:
    if not local_authors or not candidate.authors:
        return True
    return candidate.author_score >= threshold


def score_candidate(
    title: str | None,
    authors: str | None,
    candidate: AcademicMetadataCandidate,
) -> AcademicMetadataCandidate:
    local_authors = parse_authors(authors)
    candidate.title_score = title_similarity(title, candidate.title)
    candidate.author_score = author_similarity(local_authors, candidate.authors)
    if local_authors and candidate.authors:
        candidate.match_confidence = (candidate.title_score * 0.78) + (
            candidate.author_score * 0.22
        )
    else:
        candidate.match_confidence = candidate.title_score
    return candidate


def author_name_similarity(local_author: str, candidate_author: str) -> float:
    local_tokens = _author_tokens(local_author)
    candidate_tokens = _author_tokens(candidate_author)
    if not local_tokens or not candidate_tokens:
        return 0.0

    local_name = " ".join(local_tokens)
    candidate_name = " ".join(candidate_tokens)
    full_name_score = SequenceMatcher(None, local_name, candidate_name).ratio()

    local_set = set(local_tokens)
    candidate_set = set(candidate_tokens)
    token_score = len(local_set.intersection(candidate_set)) / len(local_set)

    local_surname = local_tokens[-1]
    candidate_surname = candidate_tokens[-1]
    surname_score = 1.0 if local_surname == candidate_surname else 0.0

    return max(full_name_score, token_score, surname_score * token_score)


def _author_tokens(author: str) -> list[str]:
    return [token for token in normalize_text(author).split() if len(token) > 1]

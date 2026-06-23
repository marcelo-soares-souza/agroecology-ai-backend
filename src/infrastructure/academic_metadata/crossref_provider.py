from __future__ import annotations

from typing import Any

import httpx

from src.domain.models.document_academic_metadata import AcademicMetadataCandidate
from src.domain.ports.academic_metadata_provider import AcademicMetadataProvider
from src.infrastructure.academic_metadata.parsing import (
    clean_doi,
    collapse_whitespace,
    first_string,
    strip_markup,
)


class CrossrefProvider(AcademicMetadataProvider):
    def __init__(
        self,
        mailto: str | None = None,
        timeout_seconds: float = 25.0,
    ) -> None:
        self._mailto = mailto or None
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "crossref"

    async def search(
        self, title: str, limit: int = 5
    ) -> list[AcademicMetadataCandidate]:
        params: dict[str, Any] = {"query.title": title, "rows": limit}
        if self._mailto:
            params["mailto"] = self._mailto

        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "AgroecologyMapAI/academic-metadata"},
        ) as client:
            response = await client.get("https://api.crossref.org/works", params=params)
            response.raise_for_status()
            payload = response.json()

        return [
            self._to_candidate(item)
            for item in payload.get("message", {}).get("items", [])
        ]

    def _to_candidate(self, item: dict[str, Any]) -> AcademicMetadataCandidate:
        return AcademicMetadataCandidate(
            provider=self.name,
            title=first_string(item.get("title")),
            authors=_crossref_authors(item),
            external_id=clean_doi(item.get("DOI")),
            doi=clean_doi(item.get("DOI")),
            publication_year=_crossref_year(item),
            venue=first_string(item.get("container-title")),
            publisher=collapse_whitespace(item.get("publisher")),
            citation_count=item.get("is-referenced-by-count"),
            reference_count=item.get("reference-count"),
            abstract=strip_markup(item.get("abstract")),
            source_url=item.get("URL"),
            open_access_url=_first_full_text_url(item),
            topics=_crossref_subjects(item),
            keywords=None,
            license=item.get("license"),
            funder=item.get("funder"),
        )


def _crossref_authors(item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for author in item.get("author", []):
        name = " ".join(
            part for part in (author.get("given"), author.get("family")) if part
        ).strip()
        if name:
            authors.append(name)
    return authors


def _crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = item.get(key, {}).get("date-parts")
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
    return None


def _first_full_text_url(item: dict[str, Any]) -> str | None:
    for link in item.get("link", []) or []:
        url = link.get("URL")
        if url:
            return url
    return None


def _crossref_subjects(item: dict[str, Any]) -> list[dict[str, Any]] | None:
    subjects = item.get("subject") or []
    if not subjects:
        return None
    return [{"display_name": str(subject)} for subject in subjects[:5]]

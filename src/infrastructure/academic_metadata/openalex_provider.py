from __future__ import annotations

import logging
from typing import Any

import httpx

from src.domain.models.document_academic_metadata import AcademicMetadataCandidate
from src.domain.ports.academic_metadata_provider import AcademicMetadataProvider
from src.infrastructure.academic_metadata.parsing import (
    clean_doi,
    collapse_whitespace,
    parse_year,
)
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.academic_metadata")

OPENALEX_FIELDS = ",".join(
    [
        "id",
        "doi",
        "display_name",
        "publication_year",
        "publication_date",
        "cited_by_count",
        "referenced_works_count",
        "authorships",
        "primary_location",
        "best_oa_location",
        "open_access",
        "type",
        "language",
        "topics",
        "keywords",
        "abstract_inverted_index",
        "relevance_score",
    ]
)


class OpenAlexProvider(AcademicMetadataProvider):
    def __init__(
        self,
        mailto: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 25.0,
    ) -> None:
        self._mailto = mailto or None
        self._api_key = api_key or None
        self._timeout_seconds = timeout_seconds
        self._api_key_usage_logged = False

    @property
    def name(self) -> str:
        return "openalex"

    async def search(
        self, title: str, limit: int = 5
    ) -> list[AcademicMetadataCandidate]:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "AgroecologyMapAI/academic-metadata"},
        ) as client:
            payload = await self._fetch_payload(client, f'"{title}"', limit)
            if not payload.get("results"):
                payload = await self._fetch_payload(client, title, limit)

        return [self._to_candidate(work) for work in payload.get("results", [])]

    async def _fetch_payload(
        self, client: httpx.AsyncClient, search: str, limit: int
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "search": search,
            "per-page": limit,
            "select": OPENALEX_FIELDS,
        }
        if self._mailto:
            params["mailto"] = self._mailto
        if self._api_key:
            params["api_key"] = self._api_key
            if not self._api_key_usage_logged:
                log_event(
                    logger,
                    logging.INFO,
                    "openalex_api_key_used",
                    provider=self.name,
                    api_key_configured=True,
                )
                self._api_key_usage_logged = True

        response = await client.get("https://api.openalex.org/works", params=params)
        response.raise_for_status()
        return response.json()

    def _to_candidate(self, work: dict[str, Any]) -> AcademicMetadataCandidate:
        authors = [
            authorship.get("author", {}).get("display_name")
            for authorship in work.get("authorships", [])
            if authorship.get("author", {}).get("display_name")
        ]
        topics = _openalex_named_items(work.get("topics") or [])
        keywords = _openalex_named_items(work.get("keywords") or [])

        return AcademicMetadataCandidate(
            provider=self.name,
            title=collapse_whitespace(work.get("display_name")),
            authors=authors,
            external_id=work.get("id"),
            doi=clean_doi(work.get("doi")),
            publication_year=parse_year(work.get("publication_year")),
            venue=_first_venue(work),
            publisher=_first_publisher(work),
            citation_count=work.get("cited_by_count"),
            reference_count=work.get("referenced_works_count"),
            abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
            source_url=_first_source_url(work),
            open_access_url=_first_open_access_url(work),
            topics=topics,
            keywords=keywords,
            license=None,
            funder=None,
        )


def _openalex_named_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "score": item.get("score"),
        }
        for item in items[:5]
        if item.get("display_name")
    ]


def _first_venue(work: dict[str, Any]) -> str | None:
    for location_key in ("primary_location", "best_oa_location"):
        source = (work.get(location_key) or {}).get("source") or {}
        value = source.get("display_name")
        if value:
            return value
    return None


def _first_publisher(work: dict[str, Any]) -> str | None:
    for location_key in ("primary_location", "best_oa_location"):
        source = (work.get(location_key) or {}).get("source") or {}
        for key in ("host_organization_name", "publisher"):
            value = source.get(key)
            if value:
                return value
    return None


def _first_source_url(work: dict[str, Any]) -> str | None:
    for location_key in ("primary_location", "best_oa_location"):
        location = work.get(location_key) or {}
        for key in ("landing_page_url", "pdf_url"):
            value = location.get(key)
            if value:
                return value
    return work.get("id")


def _first_open_access_url(work: dict[str, Any]) -> str | None:
    open_access = work.get("open_access") or {}
    if open_access.get("oa_url"):
        return open_access.get("oa_url")

    for location_key in ("best_oa_location", "primary_location"):
        location = work.get(location_key) or {}
        for key in ("pdf_url", "landing_page_url"):
            value = location.get(key)
            if value:
                return value
    return None


def _reconstruct_abstract(
    inverted_index: dict[str, list[int]] | None,
) -> str | None:
    if not inverted_index:
        return None

    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for index in indexes:
            positions[index] = word
    return " ".join(positions[index] for index in sorted(positions))

#!/usr/bin/env python3
"""Look up external academic metadata for local documents.

This is a read-only pilot script. It selects a small batch of documents from
PostgreSQL, searches academic metadata APIs by title, scores the candidates, and
prints a normalized JSON report. It does not write anything back to the database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from typing_extensions import Self

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/agroecology_ai"
DEFAULT_LIMIT = 5
DEFAULT_CANDIDATES_PER_SOURCE = 5
DEFAULT_MIN_CONFIDENCE = 0.88
DEFAULT_MIN_AUTHOR_CONFIDENCE = 0.80
REQUEST_TIMEOUT_SECONDS = 25.0

DEFAULT_SOURCE_ORDER = ("openalex", "crossref")
SUPPORTED_SOURCES = ("openalex", "crossref")

SEMANTIC_SCHOLAR_FIELDS = "paperId,corpusId,title,abstract,year,authors,externalIds,url,venue,publicationVenue,journal,citationCount,influentialCitationCount,referenceCount,isOpenAccess,openAccessPdf,publicationTypes,fieldsOfStudy"

OPENALEX_FIELDS = "id,doi,display_name,publication_year,publication_date,cited_by_count,referenced_works_count,authorships,primary_location,best_oa_location,open_access,type,language,topics,keywords,abstract_inverted_index,relevance_score"


class SimpleResponse:
    def __init__(self, status_code: int, content: bytes, url: str) -> None:
        self.status_code = status_code
        self.content = content
        self.url = url

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(
                f"HTTP {self.status_code} from {self.url}: {self.text[:500]}"
            )


class SimpleHttpClient:
    def __init__(self, timeout: float, headers: dict[str, str]) -> None:
        self.timeout = timeout
        self.headers = headers

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> SimpleResponse:
        query = urlencode(params or {}, doseq=True)
        request_url = f"{url}?{query}" if query else url
        request_headers = {**self.headers, **(headers or {})}
        request = Request(request_url, headers=request_headers)
        return await asyncio.to_thread(self._get_sync, request, request_url)

    def _get_sync(self, request: Request, request_url: str) -> SimpleResponse:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return SimpleResponse(
                    status_code=response.status,
                    content=response.read(),
                    url=request_url,
                )
        except HTTPError as exc:
            return SimpleResponse(
                status_code=exc.code,
                content=exc.read(),
                url=request_url,
            )
        except URLError as exc:
            raise RuntimeError(f"Request failed for {request_url}: {exc}") from exc


@dataclass(frozen=True)
class Candidate:
    source: str
    title: str | None
    authors: list[str]
    year: int | None
    doi: str | None
    citation_count: int | None
    influential_citation_count: int | None
    reference_count: int | None
    abstract: str | None
    venue: str | None
    url: str | None
    external_id: str | None
    extra: dict[str, Any]
    confidence: float = 0.0
    title_score: float = 0.0
    author_score: float = 0.0

    def with_scores(
        self, confidence: float, title_score: float, author_score: float
    ) -> Candidate:
        return Candidate(
            source=self.source,
            title=self.title,
            authors=self.authors,
            year=self.year,
            doi=self.doi,
            citation_count=self.citation_count,
            influential_citation_count=self.influential_citation_count,
            reference_count=self.reference_count,
            abstract=self.abstract,
            venue=self.venue,
            url=self.url,
            external_id=self.external_id,
            extra=self.extra,
            confidence=confidence,
            title_score=title_score,
            author_score=author_score,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "title_score": round(self.title_score, 4),
            "author_score": round(self.author_score, 4),
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "citation_count": self.citation_count,
            "influential_citation_count": self.influential_citation_count,
            "reference_count": self.reference_count,
            "abstract": self.abstract,
            "venue": self.venue,
            "url": self.url,
            "external_id": self.external_id,
            "extra": self.extra,
        }


def backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_environment() -> None:
    env_path = backend_root() / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ModuleNotFoundError:
        pass

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def mask_database_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.password is None:
        return value
    user = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{user}:***@"
    return urlunparse(parsed._replace(netloc=f"{auth}{host}{port}"))


def fetch_documents(conninfo: str, limit: int) -> list[dict[str, Any]]:
    query = """
        SELECT id, title, authors, url, filename, file_type, ingested, created_at
        FROM documents
        WHERE NULLIF(BTRIM(COALESCE(title, '')), '') IS NOT NULL
        ORDER BY created_at DESC
        LIMIT %s
    """

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError:
        return fetch_documents_with_psql(conninfo, limit)

    try:
        with psycopg.connect(conninfo, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()
    except Exception:
        return fetch_documents_with_psql(conninfo, limit)

    return [serialize_document(dict(row)) for row in rows]


def fetch_documents_with_psql(conninfo: str, limit: int) -> list[dict[str, Any]]:
    query = (
        "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json) "
        "FROM ("
        "SELECT id, title, authors, url, filename, file_type, ingested, created_at "
        "FROM documents "
        "WHERE NULLIF(BTRIM(COALESCE(title, '')), '') IS NOT NULL "
        "ORDER BY created_at DESC "
        f"LIMIT {limit}"
        ") AS t"
    )
    attempts = [
        [
            "psql",
            "-U",
            "postgres",
            "-h",
            "localhost",
            "-d",
            "agroecology_ai",
            "-X",
            "-q",
            "-t",
            "-A",
            "-c",
            query,
        ],
        ["psql", conninfo, "-X", "-q", "-t", "-A", "-c", query],
    ]

    errors: list[str] = []
    for command in attempts:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout.strip() or "[]")
        errors.append(result.stderr.strip())

    raise RuntimeError("Unable to fetch documents with psql: " + " | ".join(errors))


def serialize_document(row: dict[str, Any]) -> dict[str, Any]:
    created_at = row.get("created_at")
    if isinstance(created_at, datetime):
        row["created_at"] = created_at.isoformat()
    return row


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def collapse_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip()


def strip_markup(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    return collapse_whitespace(value)


def parse_authors(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*;\s*|\s*,\s*|\s+\band\b\s+", value)
    return [part.strip() for part in parts if part.strip()]


def author_tokens(author: str) -> list[str]:
    return [token for token in normalize_text(author).split() if len(token) > 1]


def author_name_similarity(local_author: str, candidate_author: str) -> float:
    local_tokens = author_tokens(local_author)
    candidate_tokens = author_tokens(candidate_author)
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
    document: dict[str, Any], candidate: Candidate, threshold: float
) -> bool:
    local_authors = parse_authors(document.get("authors"))
    if not local_authors or not candidate.authors:
        return True
    return candidate.author_score >= threshold


def score_candidate(document: dict[str, Any], candidate: Candidate) -> Candidate:
    local_authors = parse_authors(document.get("authors"))
    title_score = title_similarity(document.get("title"), candidate.title)
    author_score = author_similarity(local_authors, candidate.authors)
    confidence = (title_score * 0.78) + (author_score * 0.22)
    if not local_authors or not candidate.authors:
        confidence = title_score
    return candidate.with_scores(confidence, title_score, author_score)


def clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return value or None


def parse_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.match(r"^\d{4}", value):
        return int(value[:4])
    return None


def parse_crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_parts = item.get(key, {}).get("date-parts")
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
    return None


def reconstruct_openalex_abstract(
    inverted_index: dict[str, list[int]] | None,
) -> str | None:
    if not inverted_index:
        return None

    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for index in indexes:
            positions[index] = word
    return " ".join(positions[index] for index in sorted(positions))


def first_openalex_venue(work: dict[str, Any]) -> str | None:
    for location_key in ("primary_location", "best_oa_location"):
        source = (work.get(location_key) or {}).get("source") or {}
        display_name = source.get("display_name")
        if display_name:
            return display_name
    return None


def first_openalex_url(work: dict[str, Any]) -> str | None:
    for location_key in ("primary_location", "best_oa_location"):
        location = work.get(location_key) or {}
        for key in ("landing_page_url", "pdf_url"):
            value = location.get(key)
            if value:
                return value
    return work.get("id")


def semantic_scholar_headers() -> dict[str, str]:
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY") or os.getenv("S2_API_KEY")
    return {"x-api-key": api_key} if api_key else {}


async def query_semantic_scholar(
    client: SimpleHttpClient, title: str, limit: int
) -> list[Candidate]:
    response = await client.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": title,
            "limit": limit,
            "fields": SEMANTIC_SCHOLAR_FIELDS,
        },
        headers=semantic_scholar_headers(),
    )
    response.raise_for_status()
    payload = response.json()

    candidates: list[Candidate] = []
    for paper in payload.get("data", []):
        external_ids = paper.get("externalIds") or {}
        publication_venue = paper.get("publicationVenue") or {}
        journal = paper.get("journal") or {}
        open_access_pdf = paper.get("openAccessPdf") or {}

        candidates.append(
            Candidate(
                source="semantic_scholar",
                title=collapse_whitespace(paper.get("title")),
                authors=[
                    author.get("name")
                    for author in paper.get("authors", [])
                    if author.get("name")
                ],
                year=parse_year(paper.get("year")),
                doi=clean_doi(external_ids.get("DOI")),
                citation_count=paper.get("citationCount"),
                influential_citation_count=paper.get("influentialCitationCount"),
                reference_count=paper.get("referenceCount"),
                abstract=collapse_whitespace(paper.get("abstract")),
                venue=(
                    publication_venue.get("name")
                    or journal.get("name")
                    or paper.get("venue")
                ),
                url=paper.get("url") or open_access_pdf.get("url"),
                external_id=paper.get("paperId"),
                extra={
                    "corpus_id": paper.get("corpusId"),
                    "external_ids": external_ids,
                    "fields_of_study": paper.get("fieldsOfStudy"),
                    "is_open_access": paper.get("isOpenAccess"),
                    "open_access_pdf": open_access_pdf,
                    "publication_types": paper.get("publicationTypes"),
                },
            )
        )
    return candidates


async def query_openalex(
    client: SimpleHttpClient, title: str, limit: int
) -> list[Candidate]:
    payload = await fetch_openalex_payload(client, f'"{title}"', limit)
    if not payload.get("results"):
        payload = await fetch_openalex_payload(client, title, limit)

    candidates: list[Candidate] = []
    for work in payload.get("results", []):
        authors = [
            authorship.get("author", {}).get("display_name")
            for authorship in work.get("authorships", [])
            if authorship.get("author", {}).get("display_name")
        ]
        topics = work.get("topics") or []
        keywords = work.get("keywords") or []

        candidates.append(
            Candidate(
                source="openalex",
                title=collapse_whitespace(work.get("display_name")),
                authors=authors,
                year=parse_year(work.get("publication_year")),
                doi=clean_doi(work.get("doi")),
                citation_count=work.get("cited_by_count"),
                influential_citation_count=None,
                reference_count=work.get("referenced_works_count"),
                abstract=reconstruct_openalex_abstract(
                    work.get("abstract_inverted_index")
                ),
                venue=first_openalex_venue(work),
                url=first_openalex_url(work),
                external_id=work.get("id"),
                extra={
                    "publication_date": work.get("publication_date"),
                    "relevance_score": work.get("relevance_score"),
                    "type": work.get("type"),
                    "language": work.get("language"),
                    "open_access": work.get("open_access"),
                    "topics": [
                        {
                            "id": topic.get("id"),
                            "display_name": topic.get("display_name"),
                            "score": topic.get("score"),
                        }
                        for topic in topics[:5]
                    ],
                    "keywords": [
                        {
                            "id": keyword.get("id"),
                            "display_name": keyword.get("display_name"),
                            "score": keyword.get("score"),
                        }
                        for keyword in keywords[:5]
                    ],
                },
            )
        )
    return candidates


async def fetch_openalex_payload(
    client: SimpleHttpClient, search: str, limit: int
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "search": search,
        "per-page": limit,
        "select": OPENALEX_FIELDS,
    }

    api_key = os.getenv("OPENALEX_API_KEY")
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("CROSSREF_MAILTO")
    if api_key:
        params["api_key"] = api_key
    if mailto:
        params["mailto"] = mailto

    response = await client.get("https://api.openalex.org/works", params=params)
    response.raise_for_status()
    return response.json()


async def query_crossref(
    client: SimpleHttpClient, title: str, limit: int
) -> list[Candidate]:
    params: dict[str, Any] = {"query.title": title, "rows": limit}
    mailto = os.getenv("CROSSREF_MAILTO") or os.getenv("OPENALEX_MAILTO")
    if mailto:
        params["mailto"] = mailto

    response = await client.get("https://api.crossref.org/works", params=params)
    response.raise_for_status()
    payload = response.json()

    candidates: list[Candidate] = []
    for item in payload.get("message", {}).get("items", []):
        title_values = item.get("title") or []
        container_title = item.get("container-title") or []
        authors = []
        for author in item.get("author", []):
            name = " ".join(
                part for part in (author.get("given"), author.get("family")) if part
            ).strip()
            if name:
                authors.append(name)

        candidates.append(
            Candidate(
                source="crossref",
                title=collapse_whitespace(title_values[0] if title_values else None),
                authors=authors,
                year=parse_crossref_year(item),
                doi=clean_doi(item.get("DOI")),
                citation_count=item.get("is-referenced-by-count"),
                influential_citation_count=None,
                reference_count=item.get("reference-count"),
                abstract=strip_markup(item.get("abstract")),
                venue=container_title[0] if container_title else None,
                url=item.get("URL"),
                external_id=item.get("DOI"),
                extra={
                    "publisher": item.get("publisher"),
                    "type": item.get("type"),
                    "score": item.get("score"),
                    "subject": item.get("subject"),
                    "license": item.get("license"),
                    "funder": item.get("funder"),
                },
            )
        )
    return candidates


async def query_arxiv(
    client: SimpleHttpClient, title: str, limit: int
) -> list[Candidate]:
    safe_title = title.replace('"', " ")
    response = await client.get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f'ti:"{safe_title}"',
            "start": 0,
            "max_results": limit,
        },
    )
    response.raise_for_status()

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(response.text)

    candidates: list[Candidate] = []
    for entry in root.findall("atom:entry", ns):
        entry_id = collapse_whitespace(entry.findtext("atom:id", namespaces=ns))
        if not entry_id or "arxiv.org/abs/" not in entry_id:
            continue

        links = entry.findall("atom:link", ns)
        pdf_url = None
        for link in links:
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        categories = [
            category.attrib.get("term")
            for category in entry.findall("atom:category", ns)
            if category.attrib.get("term")
        ]
        primary_category = entry.find("arxiv:primary_category", ns)

        candidates.append(
            Candidate(
                source="arxiv",
                title=collapse_whitespace(entry.findtext("atom:title", namespaces=ns)),
                authors=[
                    author.findtext("atom:name", namespaces=ns) or ""
                    for author in entry.findall("atom:author", ns)
                    if author.findtext("atom:name", namespaces=ns)
                ],
                year=parse_year(entry.findtext("atom:published", namespaces=ns)),
                doi=clean_doi(entry.findtext("arxiv:doi", namespaces=ns)),
                citation_count=None,
                influential_citation_count=None,
                reference_count=None,
                abstract=collapse_whitespace(
                    entry.findtext("atom:summary", namespaces=ns)
                ),
                venue=entry.findtext("arxiv:journal_ref", namespaces=ns),
                url=entry_id,
                external_id=entry_id.removeprefix("http://arxiv.org/abs/"),
                extra={
                    "pdf_url": pdf_url,
                    "published": entry.findtext("atom:published", namespaces=ns),
                    "updated": entry.findtext("atom:updated", namespaces=ns),
                    "comment": entry.findtext("arxiv:comment", namespaces=ns),
                    "primary_category": (
                        primary_category.attrib.get("term")
                        if primary_category is not None
                        else None
                    ),
                    "categories": categories,
                },
            )
        )
    return candidates


async def query_source(
    source: str, client: SimpleHttpClient, title: str, limit: int
) -> list[Candidate]:
    if source == "semantic_scholar":
        return await query_semantic_scholar(client, title, limit)
    if source == "openalex":
        return await query_openalex(client, title, limit)
    if source == "crossref":
        return await query_crossref(client, title, limit)
    if source == "arxiv":
        return await query_arxiv(client, title, limit)
    raise ValueError(f"Unsupported source: {source}")


def selected_sources(value: str) -> tuple[str, ...]:
    if value == "all":
        return DEFAULT_SOURCE_ORDER
    return (value,)


async def enrich_documents(args: argparse.Namespace) -> dict[str, Any]:
    conninfo = database_url()
    documents = fetch_documents(conninfo, args.limit)

    report: dict[str, Any] = {
        "database": {
            "connection": mask_database_url(conninfo),
            "limit": args.limit,
            "selected_count": len(documents),
        },
        "lookup": {
            "db_only": args.db_only,
            "mode": args.mode,
            "sources": list(selected_sources(args.source)),
            "candidates_per_source": args.candidates_per_source,
            "min_confidence": args.min_confidence,
            "min_author_confidence": args.min_author_confidence,
        },
        "documents": [],
    }

    if args.db_only:
        report["documents"] = [{"document": document} for document in documents]
        return report

    headers = {"User-Agent": "AgroecologyMapAI/metadata-lookup-pilot"}

    async with SimpleHttpClient(
        timeout=REQUEST_TIMEOUT_SECONDS, headers=headers
    ) as client:
        for document in documents:
            title = document.get("title") or ""
            source_errors: dict[str, str] = {}
            candidates: list[Candidate] = []

            for source in selected_sources(args.source):
                try:
                    source_candidates = await query_source(
                        source, client, title, args.candidates_per_source
                    )
                    scored = [
                        score_candidate(document, candidate)
                        for candidate in source_candidates
                    ]
                    candidates.extend(scored)
                except Exception as exc:  # noqa: BLE001 - CLI report should continue.
                    source_errors[source] = f"{type(exc).__name__}: {exc}"
                    continue

                if args.mode == "fallback":
                    accepted_so_far = best_accepted_candidate(
                        document,
                        candidates,
                        args.min_confidence,
                        args.min_author_confidence,
                    )
                    if accepted_so_far is not None:
                        break

            candidates = sorted(
                candidates,
                key=lambda item: (item.confidence, item.citation_count or -1),
                reverse=True,
            )
            top = best_candidate(candidates)
            best = best_accepted_candidate(
                document,
                candidates,
                args.min_confidence,
                args.min_author_confidence,
            )
            match_accepted = best is not None

            report["documents"].append(
                {
                    "document": document,
                    "best_match": best.to_dict() if best else None,
                    "top_candidate": top.to_dict() if top else None,
                    "match_accepted": match_accepted,
                    "candidates": [candidate.to_dict() for candidate in candidates],
                    "errors": source_errors,
                }
            )

    return report


def best_candidate(candidates: list[Candidate]) -> Candidate | None:
    if not candidates:
        return None
    return max(
        candidates, key=lambda item: (item.confidence, item.citation_count or -1)
    )


def best_accepted_candidate(
    document: dict[str, Any],
    candidates: list[Candidate],
    min_confidence: float,
    min_author_confidence: float,
) -> Candidate | None:
    accepted = [
        candidate
        for candidate in candidates
        if candidate.confidence >= min_confidence
        and author_validation_passed(document, candidate, min_author_confidence)
    ]
    return best_candidate(accepted)


def json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Select up to 5 local documents and look up academic metadata by title."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="Number of documents selected from PostgreSQL. Defaults to 5.",
    )
    parser.add_argument(
        "--candidates-per-source",
        type=int,
        default=DEFAULT_CANDIDATES_PER_SOURCE,
        help="Number of candidates requested from each external source.",
    )
    parser.add_argument(
        "--source",
        choices=("all", *SUPPORTED_SOURCES),
        default="all",
        help="External source to query. Defaults to providers with positive matches.",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "fallback"),
        default="fallback",
        help="Query all selected sources or stop after a confident match.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="Minimum score used by fallback mode. Defaults to 0.88.",
    )
    parser.add_argument(
        "--min-author-confidence",
        type=float,
        default=DEFAULT_MIN_AUTHOR_CONFIDENCE,
        help="Minimum author similarity required when APIs return authors.",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Only print the 5 selected database records, without API calls.",
    )
    return parser


async def async_main() -> int:
    load_environment()
    parser = build_parser()
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be greater than zero")
    if args.candidates_per_source < 1:
        parser.error("--candidates-per-source must be greater than zero")
    if not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence must be between 0 and 1")
    if not 0 <= args.min_author_confidence <= 1:
        parser.error("--min-author-confidence must be between 0 and 1")

    report = await enrich_documents(args)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=json_default))
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()

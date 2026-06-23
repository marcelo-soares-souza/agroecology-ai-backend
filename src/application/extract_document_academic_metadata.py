from __future__ import annotations

import logging

from src.domain.models.document_academic_metadata import (
    AcademicMetadataCandidate,
    DocumentAcademicMetadata,
    DocumentAcademicMetadataUpsert,
)
from src.domain.ports.academic_metadata_provider import AcademicMetadataProvider
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_repository import DocumentRepository
from src.domain.services.academic_metadata_matching import (
    author_validation_passed,
    parse_authors,
    score_candidate,
)
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.academic_metadata")


class ExtractDocumentAcademicMetadata:
    def __init__(
        self,
        repo: DocumentRepository,
        metadata_repo: DocumentAcademicMetadataRepository,
        providers: list[AcademicMetadataProvider],
        min_confidence: float,
        min_author_confidence: float,
        candidates_per_provider: int = 5,
    ) -> None:
        self._repo = repo
        self._metadata_repo = metadata_repo
        self._providers = providers
        self._min_confidence = min_confidence
        self._min_author_confidence = min_author_confidence
        self._candidates_per_provider = candidates_per_provider

    async def execute(self, doc_id: str) -> DocumentAcademicMetadata | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None
        has_title = bool(doc.title and doc.title.strip())
        has_authors = bool(doc.authors and doc.authors.strip())
        if not has_title or not has_authors:
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_minimum_info_missing",
                document_id=doc.id,
                has_title=has_title,
                has_authors=has_authors,
            )
            return None

        title = (doc.title or "").strip()
        local_authors = parse_authors(doc.authors)
        candidates: list[AcademicMetadataCandidate] = []

        for provider in self._providers:
            try:
                provider_candidates = await provider.search(
                    title, limit=self._candidates_per_provider
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "academic_metadata_provider_failed",
                    provider=provider.name,
                    document_id=doc.id,
                    error=str(exc),
                )
                continue

            for candidate in provider_candidates:
                scored = score_candidate(title, doc.authors, candidate)
                if scored.match_confidence < self._min_confidence:
                    continue
                if not author_validation_passed(
                    local_authors, scored, self._min_author_confidence
                ):
                    continue
                candidates.append(scored)

        if not candidates:
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_no_candidate",
                document_id=doc.id,
            )
            return None

        best = max(candidates, key=lambda candidate: candidate.match_confidence)
        metadata = DocumentAcademicMetadataUpsert(
            document_id=doc.id,
            provider=best.provider,
            external_id=best.external_id,
            doi=best.doi,
            publication_year=best.publication_year,
            venue=best.venue,
            publisher=best.publisher,
            citation_count=best.citation_count,
            reference_count=best.reference_count,
            abstract=best.abstract,
            source_url=best.source_url,
            open_access_url=best.open_access_url,
            topics=best.topics,
            keywords=best.keywords,
            license=best.license,
            funder=best.funder,
            match_confidence=best.match_confidence,
            title_score=best.title_score,
            author_score=best.author_score,
        )
        saved = await self._metadata_repo.upsert(metadata)
        log_event(
            logger,
            logging.INFO,
            "academic_metadata_saved",
            document_id=doc.id,
            provider=saved.provider,
            confidence=saved.match_confidence,
            doi=saved.doi or "-",
        )
        return saved

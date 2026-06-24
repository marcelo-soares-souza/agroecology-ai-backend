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
from src.shared.logging_utils import (
    hash_for_log,
    log_event,
    preview_for_log,
    round_float_for_log,
)

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

    async def execute(
        self, doc_id: str, run_id: str | None = None
    ) -> DocumentAcademicMetadata | None:
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
                run_id=run_id,
                has_title=has_title,
                has_authors=has_authors,
            )
            return None

        title = (doc.title or "").strip()
        title_key = hash_for_log(title)
        title_preview = preview_for_log(title)
        local_authors = parse_authors(doc.authors)
        candidates: list[AcademicMetadataCandidate] = []
        best_scored: AcademicMetadataCandidate | None = None
        best_rejection_reason: str | None = None
        providers_queried = 0
        provider_failures = 0
        candidates_returned = 0
        candidates_scored = 0
        rejected_low_match_confidence = 0
        rejected_low_author_confidence = 0

        for provider in self._providers:
            providers_queried += 1
            try:
                provider_candidates = await provider.search(
                    title, limit=self._candidates_per_provider
                )
            except Exception as exc:
                provider_failures += 1
                log_event(
                    logger,
                    logging.WARNING,
                    "academic_metadata_provider_failed",
                    provider=provider.name,
                    document_id=doc.id,
                    run_id=run_id,
                    error_type=type(exc).__name__,
                    title_key=title_key,
                    title_preview=title_preview,
                )
                continue

            candidates_returned += len(provider_candidates)
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_provider_candidates_received",
                provider=provider.name,
                document_id=doc.id,
                run_id=run_id,
                results_count=len(provider_candidates),
                title_key=title_key,
                title_preview=title_preview,
            )

            for candidate_index, candidate in enumerate(provider_candidates, start=1):
                scored = score_candidate(title, doc.authors, candidate)
                candidates_scored += 1
                is_best_candidate = (
                    best_scored is None
                    or scored.match_confidence > best_scored.match_confidence
                )

                decision = "accepted"
                rejection_reason = "-"
                if scored.match_confidence < self._min_confidence:
                    rejected_low_match_confidence += 1
                    decision = "rejected"
                    rejection_reason = "low_match_confidence"
                elif not author_validation_passed(
                    local_authors, scored, self._min_author_confidence
                ):
                    rejected_low_author_confidence += 1
                    decision = "rejected"
                    rejection_reason = "low_author_confidence"
                else:
                    candidates.append(scored)

                if is_best_candidate:
                    best_scored = scored
                    best_rejection_reason = rejection_reason

                log_event(
                    logger,
                    logging.DEBUG,
                    "academic_metadata_candidate_evaluated",
                    document_id=doc.id,
                    run_id=run_id,
                    provider=provider.name,
                    candidate_index=candidate_index,
                    decision=decision,
                    rejection_reason=rejection_reason,
                    doi=preview_for_log(scored.doi),
                    external_id=preview_for_log(scored.external_id),
                    candidate_title_preview=preview_for_log(scored.title),
                    candidate_author_count=len(scored.authors),
                    candidate_publication_year=scored.publication_year,
                    match_confidence=round_float_for_log(scored.match_confidence),
                    title_score=round_float_for_log(scored.title_score),
                    author_score=round_float_for_log(scored.author_score),
                    min_confidence=round_float_for_log(self._min_confidence),
                    min_author_confidence=round_float_for_log(
                        self._min_author_confidence
                    ),
                )

        if not candidates:
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_no_candidate",
                document_id=doc.id,
                run_id=run_id,
                failure_reason=_no_candidate_failure_reason(
                    providers_queried=providers_queried,
                    provider_failures=provider_failures,
                    candidates_returned=candidates_returned,
                ),
                providers_queried=providers_queried,
                provider_failures=provider_failures,
                candidates_returned=candidates_returned,
                candidates_scored=candidates_scored,
                rejected_low_match_confidence=rejected_low_match_confidence,
                rejected_low_author_confidence=rejected_low_author_confidence,
                best_provider=best_scored.provider if best_scored else None,
                best_rejection_reason=best_rejection_reason,
                best_confidence=(
                    round_float_for_log(best_scored.match_confidence)
                    if best_scored
                    else None
                ),
                best_title_score=(
                    round_float_for_log(best_scored.title_score)
                    if best_scored
                    else None
                ),
                best_author_score=(
                    round_float_for_log(best_scored.author_score)
                    if best_scored
                    else None
                ),
                best_doi=preview_for_log(best_scored.doi) if best_scored else None,
                best_external_id=(
                    preview_for_log(best_scored.external_id) if best_scored else None
                ),
                min_confidence=round_float_for_log(self._min_confidence),
                min_author_confidence=round_float_for_log(self._min_author_confidence),
                title_key=title_key,
                title_preview=title_preview,
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
            run_id=run_id,
            provider=saved.provider,
            confidence=round_float_for_log(saved.match_confidence),
            title_score=round_float_for_log(saved.title_score),
            author_score=round_float_for_log(saved.author_score),
            doi=saved.doi or "-",
            external_id=preview_for_log(saved.external_id),
            title_key=title_key,
        )
        return saved


def _no_candidate_failure_reason(
    *,
    providers_queried: int,
    provider_failures: int,
    candidates_returned: int,
) -> str:
    if providers_queried == 0:
        return "no_providers_configured"
    if provider_failures >= providers_queried:
        return "all_providers_failed"
    if candidates_returned == 0 and provider_failures > 0:
        return "mixed_provider_failure_no_candidate"
    if candidates_returned == 0:
        return "no_candidates_returned"
    return "all_candidates_rejected"

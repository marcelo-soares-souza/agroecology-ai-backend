from __future__ import annotations

import asyncio
import logging

from src.application.extract_document_academic_metadata import (
    ExtractDocumentAcademicMetadata,
)
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_academic_metadata_attempt_repository import (
    DocumentAcademicMetadataAttemptRepository,
)
from src.domain.ports.document_repository import DocumentRepository
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.academic_metadata")


class RunAcademicMetadataExtraction:
    def __init__(
        self,
        repo: DocumentRepository,
        metadata_repo: DocumentAcademicMetadataRepository,
        attempt_repo: DocumentAcademicMetadataAttemptRepository,
        run_repo: AcademicMetadataRunRepository,
        extract_document_academic_metadata: ExtractDocumentAcademicMetadata,
    ) -> None:
        self._repo = repo
        self._metadata_repo = metadata_repo
        self._attempt_repo = attempt_repo
        self._run_repo = run_repo
        self._extract_document_academic_metadata = extract_document_academic_metadata

    async def execute(
        self,
        run_id: str,
        delay_seconds: int,
        force: bool = False,
        document_ids: list[str] | None = None,
    ) -> None:
        try:
            if document_ids:
                documents = await self._repo.get_many(document_ids)
                order = {
                    document_id: index for index, document_id in enumerate(document_ids)
                }
                documents = sorted(
                    documents,
                    key=lambda document: order.get(document.id, len(order)),
                )
            else:
                documents = await self._repo.list_all()

            if not force:
                filtered = []
                for doc in documents:
                    if not await self._attempt_repo.exists(doc.id):
                        filtered.append(doc)
                documents = filtered

            total = len(documents)
            await self._run_repo.mark_started(run_id, documents_total=total)
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_run_started",
                run_id=run_id,
                documents_total=total,
                delay_seconds=delay_seconds,
                force=force,
                document_count=len(document_ids or []),
            )

            processed = 0
            enriched = 0
            skipped = 0
            failed = 0

            for index, doc in enumerate(documents):
                position = index + 1
                await self._run_repo.update_progress(
                    run_id=run_id,
                    documents_processed=processed,
                    documents_enriched=enriched,
                    documents_skipped=skipped,
                    documents_failed=failed,
                    current_document_id=doc.id,
                )
                log_event(
                    logger,
                    logging.INFO,
                    "academic_metadata_document_started",
                    run_id=run_id,
                    document_id=doc.id,
                    position=position,
                    documents_total=total,
                    documents_processed=processed,
                    documents_enriched=enriched,
                    documents_skipped=skipped,
                    documents_failed=failed,
                )
                has_title = bool(doc.title and doc.title.strip())
                has_authors = bool(doc.authors and doc.authors.strip())
                if not has_title or not has_authors:
                    skipped += 1
                    await self._attempt_repo.record(
                        document_id=doc.id,
                        status="skipped",
                        last_error="Missing title or authors",
                    )
                    log_event(
                        logger,
                        logging.INFO,
                        "academic_metadata_document_skipped_minimum_info",
                        run_id=run_id,
                        document_id=doc.id,
                        position=position,
                        documents_total=total,
                        has_title=has_title,
                        has_authors=has_authors,
                    )
                else:
                    try:
                        result = await self._extract_document_academic_metadata.execute(
                            doc.id,
                            run_id=run_id,
                        )
                        if result:
                            enriched += 1
                            await self._attempt_repo.record(
                                document_id=doc.id,
                                status="enriched",
                            )
                        else:
                            skipped += 1
                            await self._attempt_repo.record(
                                document_id=doc.id,
                                status="no_match",
                            )
                    except Exception as exc:
                        failed += 1
                        await self._attempt_repo.record(
                            document_id=doc.id,
                            status="failed",
                            last_error=str(exc),
                        )
                        log_event(
                            logger,
                            logging.ERROR,
                            "academic_metadata_document_failed",
                            run_id=run_id,
                            document_id=doc.id,
                            error=str(exc),
                        )

                processed += 1
                await self._run_repo.update_progress(
                    run_id=run_id,
                    documents_processed=processed,
                    documents_enriched=enriched,
                    documents_skipped=skipped,
                    documents_failed=failed,
                    current_document_id=None,
                )
                log_event(
                    logger,
                    logging.INFO,
                    "academic_metadata_document_completed",
                    run_id=run_id,
                    document_id=doc.id,
                    position=position,
                    documents_total=total,
                    documents_processed=processed,
                    documents_enriched=enriched,
                    documents_skipped=skipped,
                    documents_failed=failed,
                )

                if index < total - 1:
                    log_event(
                        logger,
                        logging.INFO,
                        "academic_metadata_delay_started",
                        run_id=run_id,
                        delay_seconds=delay_seconds,
                        next_position=position + 1,
                        documents_total=total,
                    )
                    await asyncio.sleep(delay_seconds)

            await self._run_repo.mark_done(run_id)
            log_event(
                logger,
                logging.INFO,
                "academic_metadata_run_completed",
                run_id=run_id,
                documents_processed=processed,
                documents_enriched=enriched,
                documents_skipped=skipped,
                documents_failed=failed,
            )
        except Exception as exc:
            await self._run_repo.mark_error(run_id, str(exc))
            log_event(
                logger,
                logging.ERROR,
                "academic_metadata_run_failed",
                run_id=run_id,
                error=str(exc),
            )
            raise

from __future__ import annotations

from src.domain.models.document_academic_metadata import (
    AcademicMetadataRun,
    AcademicMetadataStatusTotals,
)
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)
from src.domain.ports.document_academic_metadata_attempt_repository import (
    DocumentAcademicMetadataAttemptRepository,
)
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)


class GetAcademicMetadataRunStatus:
    def __init__(
        self,
        run_repo: AcademicMetadataRunRepository,
        attempt_repo: DocumentAcademicMetadataAttemptRepository,
        metadata_repo: DocumentAcademicMetadataRepository,
    ) -> None:
        self._run_repo = run_repo
        self._attempt_repo = attempt_repo
        self._metadata_repo = metadata_repo

    async def execute(self) -> AcademicMetadataRun | None:
        active = await self._run_repo.get_active_run()
        if active:
            return active
        return await self._run_repo.get_latest_run()

    async def get_run(self, run_id: str) -> AcademicMetadataRun | None:
        return await self._run_repo.get(run_id)

    async def count_pending_documents(self) -> int:
        return await self._attempt_repo.count_pending()

    async def get_totals(self) -> AcademicMetadataStatusTotals:
        totals = await self._attempt_repo.count_totals()
        totals.documents_with_full_metadata = await self._metadata_repo.count_all()
        return totals

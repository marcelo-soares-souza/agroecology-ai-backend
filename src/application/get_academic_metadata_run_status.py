from __future__ import annotations

from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)
from src.domain.ports.document_academic_metadata_attempt_repository import (
    DocumentAcademicMetadataAttemptRepository,
)


class GetAcademicMetadataRunStatus:
    def __init__(
        self,
        run_repo: AcademicMetadataRunRepository,
        attempt_repo: DocumentAcademicMetadataAttemptRepository,
    ) -> None:
        self._run_repo = run_repo
        self._attempt_repo = attempt_repo

    async def execute(self) -> AcademicMetadataRun | None:
        active = await self._run_repo.get_active_run()
        if active:
            return active
        return await self._run_repo.get_latest_run()

    async def get_run(self, run_id: str) -> AcademicMetadataRun | None:
        return await self._run_repo.get(run_id)

    async def count_pending_documents(self) -> int:
        return await self._attempt_repo.count_pending()

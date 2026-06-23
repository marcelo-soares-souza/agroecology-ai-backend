from __future__ import annotations

from src.domain.models.document_academic_metadata import AcademicMetadataRun
from src.domain.ports.academic_metadata_run_repository import (
    AcademicMetadataRunRepository,
)


class GetAcademicMetadataRunStatus:
    def __init__(self, run_repo: AcademicMetadataRunRepository) -> None:
        self._run_repo = run_repo

    async def execute(self) -> AcademicMetadataRun | None:
        active = await self._run_repo.get_active_run()
        if active:
            return active
        return await self._run_repo.get_latest_run()

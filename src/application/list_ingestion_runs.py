from __future__ import annotations

from src.domain.models.ingestion_run import IngestionRun
from src.domain.ports.ingestion_repository import IngestionRepository


class ListIngestionRuns:
    def __init__(self, ingestion_repo: IngestionRepository) -> None:
        self._ingestion_repo = ingestion_repo

    async def list_all(self) -> list[IngestionRun]:
        return await self._ingestion_repo.list_all()

    async def get(self, run_id: str) -> IngestionRun | None:
        return await self._ingestion_repo.get(run_id)

    async def get_active(self) -> IngestionRun | None:
        return await self._ingestion_repo.get_active_run()

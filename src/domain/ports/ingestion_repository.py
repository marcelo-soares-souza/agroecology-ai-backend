from abc import ABC, abstractmethod

from src.domain.models.ingestion_run import IngestionRun


class IngestionRepository(ABC):
    @abstractmethod
    async def insert(self) -> IngestionRun: ...

    @abstractmethod
    async def update(
        self,
        run_id: str,
        status: str,
        chunks_indexed: int = 0,
        error: str | None = None,
    ) -> IngestionRun | None: ...

    @abstractmethod
    async def list_all(self) -> list[IngestionRun]: ...

    @abstractmethod
    async def get(self, run_id: str) -> IngestionRun | None: ...

    @abstractmethod
    async def get_ingested_ids(self, doc_ids: set[str]) -> set[str]: ...

    @abstractmethod
    async def mark_as_ingested(self, doc_ids: set[str]) -> None: ...

    @abstractmethod
    async def mark_all_not_ingested(self) -> None: ...

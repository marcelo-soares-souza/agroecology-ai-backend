from abc import ABC, abstractmethod

from src.domain.models.document import Document, DocumentCreate, DocumentUpdate


class DocumentRepository(ABC):
    @abstractmethod
    async def insert(self, doc: DocumentCreate) -> Document: ...

    @abstractmethod
    async def get(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    async def list_all(self) -> list[Document]: ...

    @abstractmethod
    async def update(self, doc_id: str, data: DocumentUpdate) -> Document | None: ...

    @abstractmethod
    async def delete(self, doc_id: str) -> Document | None: ...

    @abstractmethod
    async def filename_exists(self, filename: str) -> bool: ...

    @abstractmethod
    async def get_title_map(self) -> dict[str, str | None]: ...

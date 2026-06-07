from __future__ import annotations

from dataclasses import dataclass

from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort

_FILE_EXTENSIONS = {"pdf": ".pdf", "md": ".md", "txt": ".txt"}


@dataclass(frozen=True)
class DocumentFile:
    filename: str
    path: str
    media_type: str


class GetDocumentFile:
    def __init__(self, repo: DocumentRepository, storage: FileStoragePort) -> None:
        self._repo = repo
        self._storage = storage

    async def execute(self, doc_id: str) -> DocumentFile | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None

        ext = _FILE_EXTENSIONS.get(doc.file_type)
        if not ext:
            return None
        if not await self._storage.exists(doc.directory, doc.id, ext):
            return None

        return DocumentFile(
            filename=doc.filename,
            path=self._storage.get_path(doc.directory, doc.id, ext),
            media_type="application/pdf" if doc.file_type == "pdf" else "text/plain",
        )

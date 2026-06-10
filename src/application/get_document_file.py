from __future__ import annotations

from src.domain.dto.document_file import DocumentFile
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.config import FILE_TYPE_TO_EXT


class GetDocumentFile:
    def __init__(self, repo: DocumentRepository, storage: FileStoragePort) -> None:
        self._repo = repo
        self._storage = storage

    async def execute(self, doc_id: str) -> DocumentFile | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None

        ext = FILE_TYPE_TO_EXT.get(doc.file_type)
        if not ext:
            return None
        if not await self._storage.exists(doc.directory, doc.id, ext):
            return None

        return DocumentFile(
            filename=doc.filename,
            path=self._storage.get_path(doc.directory, doc.id, ext),
            media_type="application/pdf" if doc.file_type == "pdf" else "text/plain",
        )

from __future__ import annotations

from src.application.config import DocumentStorageConfig
from src.domain.dto.document_file import DocumentFile
from src.domain.ports.document_academic_metadata_repository import (
    DocumentAcademicMetadataRepository,
)
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.license_policy import is_full_file_access_blocked


class DocumentFileAccessBlockedError(Exception):
    pass


class GetDocumentFile:
    def __init__(
        self,
        repo: DocumentRepository,
        storage: FileStoragePort,
        academic_metadata_repo: DocumentAcademicMetadataRepository,
        config: DocumentStorageConfig,
    ) -> None:
        self._repo = repo
        self._storage = storage
        self._academic_metadata_repo = academic_metadata_repo
        self._config = config

    async def execute(self, doc_id: str) -> DocumentFile | None:
        doc = await self._repo.get(doc_id)
        if not doc:
            return None

        metadata = await self._academic_metadata_repo.get(doc_id)
        if is_full_file_access_blocked(
            doc.file_type, metadata.license if metadata is not None else None
        ):
            raise DocumentFileAccessBlockedError

        ext = self._config.file_type_to_ext.get(doc.file_type)
        if not ext:
            return None
        if not await self._storage.exists(doc.directory, doc.id, ext):
            return None

        return DocumentFile(
            filename=doc.filename,
            path=self._storage.get_path(doc.directory, doc.id, ext),
            media_type="application/pdf" if doc.file_type == "pdf" else "text/plain",
        )

from __future__ import annotations

import hashlib

from src.domain.dto.document_metadata import DocumentMetadataMap
from src.domain.models.document import Document, DocumentCreate, DocumentStats
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.config import FILE_TYPE_TO_EXT
from src.shared.uuid7 import uuid7

TitleMap = dict[str, str | None]


class ManageDocuments:
    def __init__(self, repo: DocumentRepository, storage: FileStoragePort) -> None:
        self._repo = repo
        self._storage = storage

    async def upload(
        self,
        filename: str,
        content: bytes,
        file_type: str,
        directory: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
    ) -> Document:
        sha256_hash = hashlib.sha256(content).hexdigest()
        doc_id = uuid7()
        ext = FILE_TYPE_TO_EXT.get(file_type, "")
        await self._storage.save(directory, doc_id, ext, content)

        doc = DocumentCreate(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            file_size=len(content),
            directory=directory,
            title=title,
            authors=authors,
            url=url,
            sha256=sha256_hash,
        )
        return await self._repo.insert(doc)

    async def list_all(self) -> list[Document]:
        return await self._repo.list_all()

    async def list_paginated(
        self,
        q: str | None,
        limit: int,
        offset: int,
        full_metadata: bool = False,
        publication_year: int | None = None,
    ) -> tuple[list[Document], int]:
        return await self._repo.list_paginated(
            q, limit, offset, full_metadata, publication_year
        )

    async def get_stats(self) -> DocumentStats:
        return await self._repo.get_stats()

    async def get(self, doc_id: str) -> Document | None:
        return await self._repo.get(doc_id)

    async def update_metadata(
        self,
        doc_id: str,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
    ) -> Document | None:
        from src.domain.models.document import DocumentUpdate

        return await self._repo.update(
            doc_id, DocumentUpdate(title=title, authors=authors, url=url)
        )

    async def delete(self, doc_id: str) -> Document | None:
        doc = await self._repo.delete(doc_id)
        if doc:
            ext = FILE_TYPE_TO_EXT.get(doc.file_type, "")
            await self._storage.delete(doc.directory, doc.id, ext)
        return doc

    async def filename_exists(self, filename: str) -> bool:
        return await self._repo.filename_exists(filename)

    async def sha256_exists(self, sha256: str) -> bool:
        return await self._repo.sha256_exists(sha256)

    async def get_title_map(self) -> TitleMap:
        return await self._repo.get_title_map()

    async def get_metadata_map(self) -> DocumentMetadataMap:
        return await self._repo.get_metadata_map()

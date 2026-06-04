from __future__ import annotations

import hashlib

from src.domain.models.document import Document, DocumentCreate
from src.domain.ports.document_repository import DocumentRepository
from src.shared.config import DATA_DIR
from src.shared.uuid7 import uuid7

_FILE_EXTENSIONS = {"pdf": ".pdf", "md": ".md", "txt": ".txt"}


class ManageDocuments:
    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

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
        ext = _FILE_EXTENSIONS.get(file_type, "")
        stored_name = f"{doc_id}{ext}"
        dest = DATA_DIR / directory / stored_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

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
            ext = _FILE_EXTENSIONS.get(doc.file_type, "")
            stored_name = f"{doc.id}{ext}"
            filepath = DATA_DIR / doc.directory / stored_name
            if filepath.exists():
                filepath.unlink()
        return doc

    async def filename_exists(self, filename: str) -> bool:
        return await self._repo.filename_exists(filename)

    async def sha256_exists(self, sha256: str) -> bool:
        return await self._repo.sha256_exists(sha256)

    async def get_title_map(self) -> dict[str, str | None]:
        return await self._repo.get_title_map()

    def get_file_path(self, doc: Document) -> str:
        ext = _FILE_EXTENSIONS.get(doc.file_type, "")
        stored_name = f"{doc.id}{ext}"
        return str(DATA_DIR / doc.directory / stored_name)

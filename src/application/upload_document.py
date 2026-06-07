from __future__ import annotations

import hashlib

from src.domain.models.document import DocumentCreate
from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.uuid7 import uuid7

_FILE_EXTENSIONS = {".pdf": "pdf", ".md": "md", ".txt": "txt"}
_MAX_FILE_SIZE = 50 * 1024 * 1024
_DATA_DIR_MAP = {
    ".pdf": "pdfs",
    ".md": "markdown",
    ".txt": "web",
}


class UploadDocument:
    def __init__(self, repo: DocumentRepository, storage: FileStoragePort) -> None:
        self._repo = repo
        self._storage = storage

    async def execute(
        self,
        filename: str,
        content: bytes,
        title: str | None = None,
        authors: str | None = None,
        url: str | None = None,
    ) -> dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        ext = f".{ext}"

        if ext not in _FILE_EXTENSIONS:
            raise ValueError(f"Unsupported format ({ext})")

        file_type = _FILE_EXTENSIONS[ext]
        directory = _DATA_DIR_MAP[ext]
        size = len(content)

        if size == 0:
            raise ValueError("Empty file")

        if size > _MAX_FILE_SIZE:
            raise ValueError(f"File exceeds 50 MB ({size / 1024 / 1024:.1f} MB)")

        sha256_hash = hashlib.sha256(content).hexdigest()
        if await self._repo.sha256_exists(sha256_hash):
            raise ValueError("File already uploaded (identical content)")

        doc_id = uuid7()
        await self._storage.save(directory, doc_id, ext, content)

        doc = DocumentCreate(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            file_size=size,
            directory=directory,
            title=title,
            authors=authors,
            url=url,
            sha256=sha256_hash,
        )
        created = await self._repo.insert(doc)

        return {
            "id": created.id,
            "filename": created.filename,
            "directory": created.directory,
            "size": created.file_size,
            "file_type": created.file_type,
            "should_extract_metadata": file_type == "pdf",
        }

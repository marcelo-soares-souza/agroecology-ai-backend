from __future__ import annotations

from src.domain.models.document import Document
from src.domain.ports.document_repository import DocumentRepository
from src.shared.config import DATA_DIR
from src.shared.uuid7 import uuid7


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
        doc_id = uuid7()
        ext_map = {"pdf": ".pdf", "md": ".md", "txt": ".txt"}
        ext = ext_map.get(file_type, "")
        stored_name = f"{doc_id}{ext}"
        dest = DATA_DIR / directory / stored_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

        from src.domain.models.document import DocumentCreate

        doc = DocumentCreate(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            file_size=len(content),
            directory=directory,
            title=title,
            authors=authors,
            url=url,
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
            ext_map = {"pdf": ".pdf", "md": ".md", "txt": ".txt"}
            ext = ext_map.get(doc.file_type, "")
            stored_name = f"{doc.id}{ext}"
            filepath = DATA_DIR / doc.directory / stored_name
            if filepath.exists():
                filepath.unlink()
        return doc

    async def filename_exists(self, filename: str) -> bool:
        return await self._repo.filename_exists(filename)

    async def get_title_map(self) -> dict[str, str | None]:
        return await self._repo.get_title_map()

    def get_file_path(self, doc: Document) -> str:
        ext_map = {"pdf": ".pdf", "md": ".md", "txt": ".txt"}
        ext = ext_map.get(doc.file_type, "")
        stored_name = f"{doc.id}{ext}"
        return str(DATA_DIR / doc.directory / stored_name)

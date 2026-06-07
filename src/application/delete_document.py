from __future__ import annotations

from src.application.manage_documents import ManageDocuments
from src.domain.models.document import Document
from src.domain.ports.vector_store_port import VectorStorePort


class DeleteDocument:
    def __init__(
        self,
        manage_documents: ManageDocuments,
        vector_store: VectorStorePort,
    ) -> None:
        self._manage_documents = manage_documents
        self._vector_store = vector_store

    async def execute(self, doc_id: str) -> Document | None:
        doc = await self._manage_documents.delete(doc_id)
        if not doc:
            return None

        if self._vector_store.index_exists():
            self._vector_store.delete_by_prefix(f"{doc_id}_")
        return doc

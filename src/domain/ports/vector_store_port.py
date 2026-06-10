from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.domain.dto.retrieval_result import IndexedChunk, RetrievedChunk


class VectorStorePort(ABC):
    """Port for vector storage and similarity search.

    Abstracts the vector database so the retrieval layer can work
    with different backends (e.g., LanceDB, Pinecone).
    """

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Search for the most similar chunks to a query vector.

        Args:
            query_vector: The embedding vector of the query.
            top_k: Maximum number of results to return.
            filters: Optional metadata filters.

        Returns:
            A list of RetrievedChunk results, sorted by similarity.
        """

    @abstractmethod
    def index_exists(self) -> bool:
        """Check whether the vector index has been created.

        Returns:
            True if the index already exists.
        """

    @abstractmethod
    def build_index(self, rows: list[IndexedChunk], dimension: int) -> None:
        """Create a new vector index with the given rows.

        Args:
            rows: The indexed chunks to populate the index with.
            dimension: The dimensionality of the embedding vectors.
        """

    @abstractmethod
    def add_rows(self, rows: list[IndexedChunk]) -> None:
        """Add new rows to an existing index.

        Args:
            rows: The indexed chunks to add.
        """

    @abstractmethod
    def delete_by_prefix(self, id_prefix: str) -> None:
        """Delete all rows whose ID starts with the given prefix.

        Args:
            id_prefix: The ID prefix to match for deletion.
        """

    @abstractmethod
    def get_all_rows(self) -> list[RetrievedChunk]:
        """Retrieve every row currently in the index.

        Returns:
            A list of all RetrievedChunk entries.
        """

    @abstractmethod
    def count_chunks(self) -> int:
        """Return the total number of chunks in the index.

        Returns:
            The number of indexed chunks.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the vector store."""

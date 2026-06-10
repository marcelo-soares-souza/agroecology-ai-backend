from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    """Port for generating text embeddings.

    Abstracts the embedding model so the domain layer can use
    different backends interchangeably.
    """

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: A list of text strings to embed.

        Returns:
            A list of embedding vectors, one per input text.
        """

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Generate an embedding for a single query string.

        Args:
            query: The query text to embed.

        Returns:
            The embedding vector for the query.
        """

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors.

        Returns:
            The number of dimensions in each embedding vector.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the embedding backend."""

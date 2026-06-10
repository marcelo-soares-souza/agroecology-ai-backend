from __future__ import annotations

from abc import ABC, abstractmethod


class FileStoragePort(ABC):
    """Port for file-level storage operations.

    Abstracts the file system so the domain layer can read and write
    files without depending on a specific storage backend.
    """

    @abstractmethod
    async def save(self, directory: str, doc_id: str, ext: str, content: bytes) -> None:
        """Save raw bytes to a file path derived from directory, doc_id, and ext.

        Args:
            directory: The storage directory.
            doc_id: The document identifier used in the filename.
            ext: The file extension (with or without leading dot).
            content: The file content as bytes.
        """

    @abstractmethod
    async def delete(self, directory: str, doc_id: str, ext: str) -> bool:
        """Delete a file identified by directory, doc_id, and ext.

        Args:
            directory: The storage directory.
            doc_id: The document identifier.
            ext: The file extension.

        Returns:
            True if the file was deleted, False if it did not exist.
        """

    @abstractmethod
    async def read(self, directory: str, doc_id: str, ext: str) -> bytes:
        """Read the contents of a file.

        Args:
            directory: The storage directory.
            doc_id: The document identifier.
            ext: The file extension.

        Returns:
            The file content as bytes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """

    @abstractmethod
    async def exists(self, directory: str, doc_id: str, ext: str) -> bool:
        """Check whether a file exists.

        Args:
            directory: The storage directory.
            doc_id: The document identifier.
            ext: The file extension.

        Returns:
            True if the file exists.
        """

    @abstractmethod
    def get_path(self, directory: str, doc_id: str, ext: str) -> str:
        """Return the full file system path for the given parameters.

        Args:
            directory: The storage directory.
            doc_id: The document identifier.
            ext: The file extension.

        Returns:
            The absolute file path.
        """

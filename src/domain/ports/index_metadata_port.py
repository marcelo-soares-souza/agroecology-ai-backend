from __future__ import annotations

from abc import ABC, abstractmethod


class IndexMetadataPort(ABC):
    @abstractmethod
    def read_index_version(self) -> str:
        """Return the current index version."""

    @abstractmethod
    def bump_index_version(self) -> str:
        """Increment and persist the index version."""

    @abstractmethod
    def write_schema_version(self) -> None:
        """Persist the current schema version."""

    @abstractmethod
    def check_schema_version(self) -> tuple[bool, str, str]:
        """Return whether expected and actual schema versions match."""

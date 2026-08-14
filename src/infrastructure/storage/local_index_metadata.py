from __future__ import annotations

from pathlib import Path

from src.domain.ports.index_metadata_port import IndexMetadataPort
from src.shared.config import INDEX_DIR


class LocalIndexMetadata(IndexMetadataPort):
    def __init__(
        self,
        index_dir: Path | None = None,
        current_schema_version: str = "3",
    ) -> None:
        self._index_dir = index_dir or INDEX_DIR
        self._index_version_file = self._index_dir / "index_version.txt"
        self._schema_version_file = self._index_dir / "schema_version.txt"
        self._current_schema_version = current_schema_version

    def read_index_version(self) -> str:
        try:
            return self._index_version_file.read_text().strip()
        except (FileNotFoundError, OSError):
            return "0"

    def _write_index_version(self, version: str) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index_version_file.write_text(version.strip())

    def bump_index_version(self) -> str:
        current = self.read_index_version()
        try:
            next_version = str(int(current) + 1)
        except ValueError:
            from datetime import UTC, datetime

            next_version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        self._write_index_version(next_version)
        return next_version

    def write_schema_version(self) -> None:
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._schema_version_file.write_text(self._current_schema_version)

    def check_schema_version(self) -> tuple[bool, str, str]:
        expected = self._current_schema_version
        try:
            actual = self._schema_version_file.read_text().strip()
        except (FileNotFoundError, OSError):
            return False, expected, "(no version file)"
        return actual == expected, expected, actual

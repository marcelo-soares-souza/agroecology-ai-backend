from __future__ import annotations

from pathlib import Path

from src.domain.ports.file_storage_port import FileStoragePort
from src.shared.config import DATA_DIR


class LocalFileStorage(FileStoragePort):
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DATA_DIR

    async def save(self, directory: str, doc_id: str, ext: str, content: bytes) -> None:
        dest = self._data_dir / directory / f"{doc_id}{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

    async def delete(self, directory: str, doc_id: str, ext: str) -> bool:
        filepath = self._data_dir / directory / f"{doc_id}{ext}"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    async def read(self, directory: str, doc_id: str, ext: str) -> bytes:
        filepath = self._data_dir / directory / f"{doc_id}{ext}"
        return filepath.read_bytes()

    async def exists(self, directory: str, doc_id: str, ext: str) -> bool:
        filepath = self._data_dir / directory / f"{doc_id}{ext}"
        return filepath.exists()

    def get_path(self, directory: str, doc_id: str, ext: str) -> str:
        return str(self._data_dir / directory / f"{doc_id}{ext}")

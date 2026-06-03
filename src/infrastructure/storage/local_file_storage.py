from __future__ import annotations

from pathlib import Path

from src.shared.config import DATA_DIR


class LocalFileStorage:
    def __init__(self) -> None:
        self._root = DATA_DIR

    def save(self, directory: str, filename: str, content: bytes) -> Path:
        dest = self._root / directory / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return dest

    def get_path(self, directory: str, filename: str) -> Path:
        return self._root / directory / filename

    def exists(self, directory: str, filename: str) -> bool:
        return self.get_path(directory, filename).exists()

    def delete(self, directory: str, filename: str) -> None:
        filepath = self.get_path(directory, filename)
        if filepath.exists():
            filepath.unlink()

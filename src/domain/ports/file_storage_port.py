from abc import ABC, abstractmethod


class FileStoragePort(ABC):
    @abstractmethod
    async def save(
        self, directory: str, doc_id: str, ext: str, content: bytes
    ) -> None: ...

    @abstractmethod
    async def delete(self, directory: str, doc_id: str, ext: str) -> bool: ...

    @abstractmethod
    async def read(self, directory: str, doc_id: str, ext: str) -> bytes: ...

    @abstractmethod
    async def exists(self, directory: str, doc_id: str, ext: str) -> bool: ...

    @abstractmethod
    def get_path(self, directory: str, doc_id: str, ext: str) -> str: ...

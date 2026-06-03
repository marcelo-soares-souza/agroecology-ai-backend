from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    enabled: bool

    @abstractmethod
    def get(self, key: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def set(self, key: str, value: dict[str, Any]) -> None: ...

    @abstractmethod
    def hit_count(self) -> int: ...

    @abstractmethod
    def close(self) -> None: ...

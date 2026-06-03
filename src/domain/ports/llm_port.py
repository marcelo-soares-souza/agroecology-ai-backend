from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str: ...

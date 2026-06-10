from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMPort(ABC):
    """Port for language model text completion.

    Abstracts the LLM provider so the domain layer is not coupled
    to a specific model or API.
    """

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, **kwargs: Any) -> str:
        """Generate a completion from the language model.

        Args:
            system_prompt: The system instruction.
            user_prompt: The user message.
            **kwargs: Additional provider-specific parameters.

        Returns:
            The generated text response.
        """

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the LLM client."""

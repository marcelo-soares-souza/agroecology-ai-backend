from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageResult:
    """A simple text message response DTO.

    Attributes:
        message: The message text.
    """

    message: str

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuggestionFile:
    filename: str
    path: str
    media_type: str

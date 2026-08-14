from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ChatMessage | None:
        role = value.get("role")
        content = value.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            return None
        role = role.strip()
        content = content.strip()
        if not role or not content:
            return None
        return cls(role=role, content=content)

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

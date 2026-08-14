from __future__ import annotations

import re
from collections.abc import Sequence

from src.domain.dto.chat_message import ChatMessage

CONTEXT_DEPENDENT_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper|explain)\b",
        re.IGNORECASE,
    ),
)

_SHORT_QUESTION_WORD_THRESHOLD = 4


def find_last_message(history: Sequence[ChatMessage], role: str) -> str:
    for message in reversed(history):
        if message.role == role and message.content:
            return message.content
    return ""


def is_context_dependent_question(question: str) -> bool:
    compact_question = " ".join(question.strip().split())
    if not compact_question:
        return False
    if len(compact_question.split()) <= _SHORT_QUESTION_WORD_THRESHOLD:
        return True
    return any(
        pattern.search(compact_question) for pattern in CONTEXT_DEPENDENT_PATTERNS
    )

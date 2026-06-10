"""Conversation history inspection utilities for query rewrite decisions."""

from __future__ import annotations

import re
from typing import Any

_CONTEXT_DEPENDENT_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper|explain)\b",
        re.IGNORECASE,
    ),
)

_SHORT_QUESTION_WORD_THRESHOLD = 4


def find_last_message(history: list[dict[str, Any]], role: str) -> str:
    """Find the last message in the history from a given role.

    Args:
        history: The conversation history as a list of role/content dicts.
        role: The role to search for (e.g., 'user', 'assistant').

    Returns:
        The content of the last matching message, or an empty string if none found.
    """
    for message in reversed(history):
        if message.get("role") == role and message.get("content"):
            return str(message["content"])
    return ""


def is_context_dependent_question(question: str) -> bool:
    """Determine whether a question likely depends on previous conversation context.

    Uses word count and regex patterns to detect pronouns, follow-up phrases,
    and short questions that typically reference earlier turns.

    Args:
        question: The user's question text.

    Returns:
        True if the question appears to be context-dependent.
    """
    compact_question = " ".join(question.strip().split())
    if not compact_question:
        return False
    if len(compact_question.split()) <= _SHORT_QUESTION_WORD_THRESHOLD:
        return True
    return any(
        pattern.search(compact_question) for pattern in _CONTEXT_DEPENDENT_PATTERNS
    )

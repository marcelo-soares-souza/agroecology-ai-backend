from __future__ import annotations

import logging
import re
from typing import Any

from src.domain.ports.query_rewrite_port import QueryRewritePort

logger = logging.getLogger(__name__)

_ELIPSIS_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper|explain)\b",
        re.IGNORECASE,
    ),
)

_CONTRAST_PATTERNS = (
    re.compile(
        r"\b(but what about|but|however|on the other hand|what about|how about)\b",
        re.IGNORECASE,
    ),
)

_SHORT_QUESTION_WORDS = 6

_FALLBACK_PROMPT = """Rewrite this follow-up question into a standalone question
that includes all necessary context from the conversation.
Keep it concise. Do NOT answer it. Return ONLY the rewritten question, no extra text.

Current question: {question}

Conversation history:
{history}

Rewritten standalone question:"""


class LLMQueryRewriter(QueryRewritePort):
    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def rewrite(self, question: str, history: list[dict]) -> str:
        if not history:
            return question

        if not self._is_context_dependent(question):
            return question

        heuristic_result = self._heuristic_rewrite(question, history)
        if heuristic_result and heuristic_result != question:
            logger.info(
                "query_rewrite_heuristic original=%r rewritten=%r",
                question[:80],
                heuristic_result[:80],
            )
            return heuristic_result

        return self._llm_rewrite(question, history)

    @staticmethod
    def _is_context_dependent(question: str) -> bool:
        compact = " ".join(question.strip().split())
        if not compact:
            return False
        if len(compact.split()) <= _SHORT_QUESTION_WORDS:
            return True
        for pattern in _ELIPSIS_PATTERNS:
            if pattern.search(compact):
                return True
        return False

    @staticmethod
    def _heuristic_rewrite(question: str, history: list[dict]) -> str:
        last_user = _find_last_message(history, "user")
        last_assistant = _find_last_message(history, "assistant")

        if not last_user and not last_assistant:
            return question

        compact = " ".join(question.strip().split())

        # Continuation / more detail
        for pattern in _ELIPSIS_PATTERNS:
            if pattern.search(compact):
                parts = []
                if last_user:
                    parts.append(
                        f"Based on the previous question about: {_snip(last_user)}"
                    )
                return f"{' '.join(parts)} {question}"

        # Contrast
        for pattern in _CONTRAST_PATTERNS:
            if pattern.search(compact):
                parts = []
                if last_user:
                    parts.append(f"In contrast to: {_snip(last_user)}")
                return f"{' '.join(parts)} {question}"

        # Short question (elipsis)
        if len(compact.split()) <= _SHORT_QUESTION_WORDS and last_user:
            return f"Regarding: {_snip(last_user)}. {question}"

        return question

    def _llm_rewrite(self, question: str, history: list[dict]) -> str:
        if self._llm is None:
            return question

        history_text = "\n".join(
            f"{m.get('role', '?')}: {_snip(str(m.get('content', '')))}"
            for m in history[-4:]
        )

        try:
            result = self._llm.complete(
                system_prompt="You are a query rewriter. Return only the rewritten question.",
                user_prompt=_FALLBACK_PROMPT.format(
                    question=question, history=history_text
                ),
                temperature=0.0,
                max_tokens=200,
            )
            rewritten = result.strip().strip('"').strip("'")
            if rewritten and len(rewritten) > 3:
                logger.info(
                    "query_rewrite_llm original=%r rewritten=%r",
                    question[:80],
                    rewritten[:80],
                )
                return rewritten
        except Exception as e:
            logger.warning("query_rewrite_llm_failed error=%s", e)

        return question


def _find_last_message(history: list[dict], role: str) -> str:
    for m in reversed(history):
        if m.get("role") == role and m.get("content"):
            return str(m["content"])
    return ""


def _snip(text: str, max_chars: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:max_chars]

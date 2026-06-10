from __future__ import annotations

import logging
import re
from typing import Any

from src.domain.ports.query_rewrite_port import QueryRewritePort
from src.shared.history_utils import (
    _CONTEXT_DEPENDENT_PATTERNS,
    find_last_message,
    is_context_dependent_question,
)
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.llm")

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

        if not is_context_dependent_question(question):
            return question

        heuristic_result = self._heuristic_rewrite(question, history)
        if heuristic_result and heuristic_result != question:
            log_event(
                logger,
                logging.INFO,
                "query_rewrite_heuristic",
                original=question[:80],
                rewritten=heuristic_result[:80],
            )
            return heuristic_result

        return self._llm_rewrite(question, history)

    @staticmethod
    def _heuristic_rewrite(question: str, history: list[dict]) -> str:
        last_user = find_last_message(history, "user")
        last_assistant = find_last_message(history, "assistant")

        if not last_user and not last_assistant:
            return question

        compact = " ".join(question.strip().split())

        for pattern in _CONTEXT_DEPENDENT_PATTERNS:
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
                user_prompt=_FALLBACK_PROMPT.replace("{question}", question).replace(
                    "{history}", history_text
                ),
                temperature=0.0,
                max_tokens=200,
            )
            rewritten = result.strip().strip('"').strip("'")
            if rewritten and len(rewritten) > 3:
                log_event(
                    logger,
                    logging.INFO,
                    "query_rewrite_llm",
                    original=question[:80],
                    rewritten=rewritten[:80],
                )
                return rewritten
        except Exception as e:
            log_event(logger, logging.WARNING, "query_rewrite_llm_failed", error=e)

        return question


def _snip(text: str, max_chars: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:max_chars]

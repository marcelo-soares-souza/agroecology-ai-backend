from __future__ import annotations

import re

from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.llm_port import LLMPort
from src.domain.services.retriever import RetrieverService
from src.shared.config import HYBRID_TOP_K, SYSTEM_PROMPT, USER_PROMPT

_CONTEXT_DEPENDENT_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper)\b",
        re.IGNORECASE,
    ),
)
_MAX_HISTORY_SNIPPET_CHARS = 500


class AskQuestion:
    def __init__(
        self,
        retriever: RetrieverService,
        llm: LLMPort,
        doc_repo: DocumentRepository,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._doc_repo = doc_repo

    def execute(
        self,
        question: str,
        top_k: int | None = None,
        title_map: dict[str, str | None] | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        search_query = self._build_search_query(question, history or [])
        retrieved = self._retriever.hybrid_search(
            search_query,
            top_k=top_k or HYBRID_TOP_K,
        )

        context = self._build_context(retrieved)
        answer = self._llm.complete(
            SYSTEM_PROMPT,
            USER_PROMPT.format(context=context, question=question),
            history=history,
        )

        sources = []
        for node in retrieved:
            dist = node.get("_distance", 0)
            score = 1.0 / (1.0 + float(dist)) if dist else 0.0
            meta = {
                "source": node.get("source", "unknown"),
                "chunk_index": node.get("chunk_index", 0),
                "search_type": node.get("_search_type", "unknown"),
            }
            if title_map:
                title = title_map.get(meta["source"])
                if title:
                    meta["title"] = title
            sources.append(
                {
                    "text": node["text"][:300],
                    "score": round(score, 4),
                    "metadata": meta,
                }
            )

        return {"answer": answer, "sources": sources}

    @staticmethod
    def _build_context(retrieved: list[dict]) -> str:
        parts = []
        for i, r in enumerate(retrieved, 1):
            source = r.get("source", "unknown")
            text = r["text"].strip()
            parts.append(f"[{i}] (source: {source})\n{text}")
        return "\n\n".join(parts)

    @classmethod
    def _build_search_query(cls, question: str, history: list[dict]) -> str:
        if not history or not cls._is_context_dependent_question(question):
            return question

        last_user = cls._find_last_message(history, "user")
        last_assistant = cls._find_last_message(history, "assistant")
        if not last_user and not last_assistant:
            return question

        snippets = [f"Current follow-up question: {question.strip()}"]
        if last_user:
            snippets.append(
                f"Previous user question: {cls._normalize_snippet(last_user)}"
            )
        if last_assistant:
            snippets.append(
                "Previous assistant answer: "
                f"{cls._normalize_snippet(last_assistant)}"
            )
        return "\n".join(snippets)

    @classmethod
    def _is_context_dependent_question(cls, question: str) -> bool:
        compact_question = " ".join(question.strip().split())
        if not compact_question:
            return False
        if len(compact_question.split()) <= 4:
            return True
        return any(
            pattern.search(compact_question)
            for pattern in _CONTEXT_DEPENDENT_PATTERNS
        )

    @staticmethod
    def _find_last_message(history: list[dict], role: str) -> str:
        for message in reversed(history):
            if message.get("role") == role and message.get("content"):
                return str(message["content"])
        return ""

    @staticmethod
    def _normalize_snippet(content: str) -> str:
        compact_content = " ".join(content.split())
        return compact_content[:_MAX_HISTORY_SNIPPET_CHARS]

from __future__ import annotations

import logging
import re

from src.domain.ports.llm_port import LLMPort
from src.domain.ports.query_rewrite_port import QueryRewritePort
from src.domain.services.retriever import RetrieverService
from src.shared.config import RERANK_TOP_K, SYSTEM_PROMPT, USER_PROMPT
from src.shared.logging_utils import log_event

_CONTEXT_DEPENDENT_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper|explain)\b",
        re.IGNORECASE,
    ),
)

_MAX_HISTORY_SNIPPET_CHARS = 500
logger = logging.getLogger("agroecology.rag")


def _normalize_scores(retrieved: list[dict]) -> None:
    by_type: dict[str, list[dict]] = {}
    for r in retrieved:
        st = r.get("_search_type", "unknown")
        by_type.setdefault(st, []).append(r)

    for st, items in by_type.items():
        if st == "vector":
            for r in items:
                dist = float(r.get("_distance", 0))
                similarity = 1.0 - max(0.0, min(2.0, dist))
                r["_score"] = round(similarity, 4)
                r["_score_type"] = "cosine_similarity"
        elif st == "bm25":
            raw_scores = [float(r.get("_distance", 0)) for r in items]
            min_s, max_s = min(raw_scores), max(raw_scores)
            for r in items:
                raw = float(r.get("_distance", 0))
                if max_s > min_s:
                    r["_score"] = round((raw - min_s) / (max_s - min_s), 4)
                else:
                    r["_score"] = 1.0
                r["_score_type"] = "bm25_normalized"
        elif st == "rerank":
            for r in items:
                raw = float(r.get("_rerank_score", r.get("_distance", 0)))
                r["_score"] = round(raw, 4)
                r["_score_type"] = "reranker_logit"


class AskQuestion:
    def __init__(
        self,
        retriever: RetrieverService,
        llm: LLMPort,
        query_rewriter: QueryRewritePort | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._query_rewriter = query_rewriter

    def execute(
        self,
        question: str,
        top_k: int | None = None,
        title_map: dict[str, str | None] | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        follow_up = bool(history) and self._is_context_dependent_question(question)
        log_event(
            logger,
            logging.INFO,
            "rag_question_started",
            question_chars=len(question),
            top_k=top_k or RERANK_TOP_K,
            history_messages=len(history or []),
            follow_up_detected=follow_up,
        )
        search_query = question
        if self._query_rewriter and history:
            search_query = self._query_rewriter.rewrite(question, history)
        retrieved = self._retriever.hybrid_search(
            search_query,
            top_k=top_k or RERANK_TOP_K,
        )

        # Enrich chunks with document metadata from title_map
        if title_map:
            for node in retrieved:
                source = node.get("source", "")
                doc_title = title_map.get(source)
                if doc_title:
                    node["_title"] = doc_title

        context = self._build_context(retrieved)
        answer_history = history if follow_up else []
        answer = self._llm.complete(
            SYSTEM_PROMPT,
            USER_PROMPT.replace("{context}", context).replace("{question}", question),
            history=answer_history,
        )

        _normalize_scores(retrieved)

        sources = []
        for rank, node in enumerate(retrieved, 1):
            meta = {
                "source": node.get("source", "unknown"),
                "chunk_index": node.get("chunk_index", 0),
                "search_type": node.get("_search_type", "unknown"),
            }
            source_name = str(node.get("source", "")).rsplit("/", 1)[-1]
            doc_id = source_name.rsplit(".", 1)[0]
            if doc_id:
                meta["document_id"] = doc_id
            if title_map:
                title = title_map.get(meta["source"])
                if title:
                    meta["title"] = title
            # Structural metadata from parsed chunks
            for field in ("page_start", "page_end", "section_title", "block_types"):
                val = node.get(field, "")
                if val:
                    meta[field] = val
            sources.append(
                {
                    "text": node["text"][:300],
                    "score": node.get("_score", 0.0),
                    "score_type": node.get("_score_type", "unknown"),
                    "rank": rank,
                    "metadata": meta,
                }
            )

        log_event(
            logger,
            logging.INFO,
            "rag_question_completed",
            question_chars=len(question),
            retrieved_sources=len(sources),
            answer_chars=len(answer),
            search_query_rewritten=search_query != question,
        )
        return {"answer": answer, "sources": sources}

    @staticmethod
    def _build_context(retrieved: list[dict]) -> str:
        parts = []
        for i, r in enumerate(retrieved, 1):
            source = r.get("source", "unknown")
            text = r["text"].strip()

            lines = [f"[{i}]"]
            title = r.get("title", "") or r.get("_title", "")
            authors = r.get("authors", "") or r.get("_authors", "")
            year = r.get("year", "") or r.get("_year", "")
            section = r.get("section_title", "") or r.get("_section_title", "")
            page_start = r.get("page_start", 0) or r.get("_page_start", 0)
            page_end = r.get("page_end", 0) or r.get("_page_end", 0)

            if title:
                lines.append(f"Title: {title}")
            if authors:
                lines.append(f"Authors: {authors}")
            if year:
                lines.append(f"Year: {year}")
            if section:
                lines.append(f"Section: {section}")

            page_info = ""
            if page_start and page_end and page_start != page_end:
                page_info = f", pp. {page_start}-{page_end}"
            elif page_start:
                page_info = f", p. {page_start}"

            if page_info:
                lines.append(f"Pages{page_info}")

            lines.append(f"Source: {source}")
            lines.append(f"Text:\n{text}")
            parts.append("\n".join(lines))

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
                f"Previous assistant answer: {cls._normalize_snippet(last_assistant)}"
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
            pattern.search(compact_question) for pattern in _CONTEXT_DEPENDENT_PATTERNS
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

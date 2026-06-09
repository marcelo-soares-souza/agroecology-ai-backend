import logging
import re
from typing import Any

from lingua import Language, LanguageDetectorBuilder

from src.domain.dto.answer_result import AnswerResult, SourceResult
from src.domain.dto.retrieval_result import RetrievedChunk
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.query_rewrite_port import QueryRewritePort
from src.domain.services.retriever import RetrieverService
from src.shared.config import (
    LLM_CONTEXT_CHARS_BUDGET,
    LLM_CONTEXT_MAX_CHUNKS,
    LLM_CONTEXT_RETRY_MAX_CHUNKS,
    LLM_CHUNK_MAX_CHARS,
    RERANK_TOP_K,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
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
_LANGUAGE_PATTERN_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "Portuguese",
        (
            re.compile(r"[ãõáàâêéíóôúç]"),
            re.compile(
                r"\b(o que|como|quais|qual|porque|por que|para|uma|não|voc[eê]|sobre)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "Spanish",
        (
            re.compile(r"[ñ¿¡]"),
            re.compile(
                r"\b(qué|como|cu[aá]l|cu[aá]les|porque|por qu[eé]|para|una|sobre|usted)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "French",
        (
            re.compile(r"[àâçéèêëîïôùûüœ]"),
            re.compile(
                r"\b(quoi|comment|quel|quelle|quels|quelles|pourquoi|avec|une|sur)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "English",
        (
            re.compile(
                r"\b(what|how|which|why|when|where|can|could|would|should|about|the|is|are)\b",
                re.IGNORECASE,
            ),
        ),
    ),
)
_LANGUAGE_FALLBACK_LABEL = "the same language as the current user question"
_LINGUA_LANGUAGES = (
    Language.ENGLISH,
    Language.PORTUGUESE,
    Language.SPANISH,
    Language.FRENCH,
)
_LINGUA_LANGUAGE_NAMES = {
    Language.ENGLISH: "English",
    Language.PORTUGUESE: "Portuguese",
    Language.SPANISH: "Spanish",
    Language.FRENCH: "French",
}
_LINGUA_DETECTOR = LanguageDetectorBuilder.from_languages(*_LINGUA_LANGUAGES).build()
logger = logging.getLogger("agroecology.rag")


def _normalize_scores(retrieved: list[RetrievedChunk]) -> None:
    by_type: dict[str, list[RetrievedChunk]] = {}
    for chunk in retrieved:
        st = chunk.search_type
        by_type.setdefault(st, []).append(chunk)

    for st, items in by_type.items():
        if st == "vector":
            for chunk in items:
                dist = float(chunk.distance or 0.0)
                similarity = 1.0 - max(0.0, min(2.0, dist))
                chunk.score = round(similarity, 4)
                chunk.score_type = "cosine_similarity"
        elif st == "bm25":
            raw_scores = [float(chunk.distance or 0.0) for chunk in items]
            min_s, max_s = min(raw_scores), max(raw_scores)
            for chunk in items:
                raw = float(chunk.distance or 0.0)
                if max_s > min_s:
                    chunk.score = round((raw - min_s) / (max_s - min_s), 4)
                else:
                    chunk.score = 1.0
                chunk.score_type = "bm25_normalized"
        elif st == "rerank":
            for chunk in items:
                raw = float(chunk.rerank_score or chunk.distance or 0.0)
                chunk.score = round(raw, 4)
                chunk.score_type = "reranker_logit"


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
        history: list[dict[str, Any]] | None = None,
    ) -> AnswerResult:
        normalized_history: list[dict[str, Any]] = history or []
        follow_up = bool(normalized_history) and self._is_context_dependent_question(
            question
        )
        (
            expected_language,
            language_confidence,
            language_source,
        ) = self._resolve_answer_language(question, normalized_history, follow_up)
        log_event(
            logger,
            logging.INFO,
            "rag_question_started",
            question_chars=len(question),
            top_k=top_k or RERANK_TOP_K,
            history_messages=len(normalized_history),
            follow_up_detected=follow_up,
            expected_language=expected_language,
            language_confidence=language_confidence,
            language_source=language_source,
        )
        search_query = question
        if self._query_rewriter and normalized_history:
            search_query = self._query_rewriter.rewrite(question, normalized_history)
        retrieved = self._retriever.hybrid_search(
            search_query,
            top_k=top_k or RERANK_TOP_K,
        )

        # Enrich chunks with document metadata from title_map
        if title_map:
            for chunk in retrieved:
                doc_title = title_map.get(chunk.source)
                if doc_title:
                    chunk.title = doc_title

        answer_history: list[dict[str, Any]] = normalized_history if follow_up else []
        context_chunks = self._select_context_chunks(retrieved)
        log_event(
            logger,
            logging.INFO,
            "rag_context_selected",
            retrieved_count=len(retrieved),
            selected_count=len(context_chunks),
            selected_chars=sum(len(chunk.text) for chunk in context_chunks),
            history_messages=len(answer_history),
        )
        answer = self._generate_answer(
            question,
            context_chunks,
            answer_history,
            expected_language,
        )
        if not answer and len(context_chunks) > 1:
            retry_chunks = context_chunks[:LLM_CONTEXT_RETRY_MAX_CHUNKS]
            log_event(
                logger,
                logging.WARNING,
                "rag_empty_answer_retrying",
                initial_context_chunks=len(context_chunks),
                retry_context_chunks=len(retry_chunks),
                initial_context_chars=sum(len(chunk.text) for chunk in context_chunks),
                retry_context_chars=sum(len(chunk.text) for chunk in retry_chunks),
                question_chars=len(question),
            )
            retry_answer = self._generate_answer(
                question,
                retry_chunks,
                answer_history,
                expected_language,
            )
            if retry_answer:
                log_event(
                    logger,
                    logging.INFO,
                    "rag_empty_answer_recovered",
                    initial_context_chunks=len(context_chunks),
                    retry_context_chunks=len(retry_chunks),
                    question_chars=len(question),
                )
                answer = retry_answer
                context_chunks = retry_chunks

        _normalize_scores(context_chunks)

        sources = []
        for rank, chunk in enumerate(context_chunks, 1):
            source = chunk.source or "unknown"
            meta = {
                "source": source,
                "chunk_index": chunk.chunk_index,
                "search_type": chunk.search_type,
            }
            source_name = chunk.source.rsplit("/", 1)[-1]
            doc_id = source_name.rsplit(".", 1)[0]
            if doc_id:
                meta["document_id"] = doc_id
            if title_map:
                title = title_map.get(source)
                if title:
                    meta["title"] = title
            for field in ("page_start", "page_end", "section_title", "block_types"):
                val = getattr(chunk, field)
                if val:
                    meta[field] = val
            sources.append(
                SourceResult(
                    text=chunk.text[:300],
                    score=chunk.score,
                    score_type=chunk.score_type,
                    rank=rank,
                    metadata=meta,
                )
            )

        log_event(
            logger,
            logging.INFO,
            "rag_question_completed",
            question_chars=len(question),
            retrieved_sources=len(sources),
            answer_chars=len(answer),
            search_query_rewritten=search_query != question,
            expected_language=expected_language,
            language_confidence=language_confidence,
            language_source=language_source,
        )
        return AnswerResult(answer=answer, sources=sources)

    @staticmethod
    def _build_context(retrieved: list[RetrievedChunk]) -> str:
        parts = []
        for i, chunk in enumerate(retrieved, 1):
            source = chunk.source or "unknown"
            text = chunk.text.strip()

            lines = [f"[{i}]"]
            title = chunk.title
            authors = chunk.authors
            year = chunk.year
            section = chunk.section_title
            page_start = chunk.page_start or 0
            page_end = chunk.page_end or 0

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

    def _generate_answer(
        self,
        question: str,
        context_chunks: list[RetrievedChunk],
        answer_history: list[dict[str, Any]],
        expected_language: str,
    ) -> str:
        context = self._build_context(context_chunks)
        return self._llm.complete(
            SYSTEM_PROMPT,
            USER_PROMPT.replace("{context}", context)
            .replace("{question}", question)
            .replace("{expected_language}", expected_language),
            history=answer_history,
        )

    @staticmethod
    def _select_context_chunks(retrieved: list[RetrievedChunk]) -> list[RetrievedChunk]:
        selected: list[RetrievedChunk] = []
        used_chars = 0

        for chunk in retrieved:
            if len(selected) >= LLM_CONTEXT_MAX_CHUNKS:
                break

            trimmed_text = chunk.text.strip()[:LLM_CHUNK_MAX_CHARS].strip()
            if not trimmed_text:
                continue

            chunk_copy = RetrievedChunk.from_dict(chunk.to_dict())
            chunk_copy.text = trimmed_text

            estimated_chars = len(trimmed_text) + 300
            if selected and used_chars + estimated_chars > LLM_CONTEXT_CHARS_BUDGET:
                break

            selected.append(chunk_copy)
            used_chars += estimated_chars

        return selected or retrieved[:1]

    @classmethod
    def _build_search_query(cls, question: str, history: list[dict[str, Any]]) -> str:
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
    def _find_last_message(history: list[dict[str, Any]], role: str) -> str:
        for message in reversed(history):
            if message.get("role") == role and message.get("content"):
                return str(message["content"])
        return ""

    @staticmethod
    def _normalize_snippet(content: str) -> str:
        compact_content = " ".join(content.split())
        return compact_content[:_MAX_HISTORY_SNIPPET_CHARS]

    @staticmethod
    def _detect_question_language(question: str) -> tuple[str, str]:
        compact_question = " ".join(question.strip().split())
        if not compact_question:
            return _LANGUAGE_FALLBACK_LABEL, "low"

        lingua_result = AskQuestion._detect_with_lingua(compact_question)
        if lingua_result is not None:
            return lingua_result

        best_language = ""
        best_score = 0

        for language_name, patterns in _LANGUAGE_PATTERN_RULES:
            score = sum(1 for pattern in patterns if pattern.search(compact_question))
            if score > best_score:
                best_language = language_name
                best_score = score

        if not best_language:
            return _LANGUAGE_FALLBACK_LABEL, "low"

        if best_score >= 2 or len(compact_question.split()) >= 6:
            return best_language, "high"
        if len(compact_question.split()) >= 3:
            return best_language, "medium"
        return best_language, "low"

    @classmethod
    def _resolve_answer_language(
        cls,
        question: str,
        history: list[dict[str, Any]],
        follow_up: bool,
    ) -> tuple[str, str, str]:
        detected_language, confidence = cls._detect_question_language(question)
        if confidence in {"high", "medium"}:
            return detected_language, confidence, "current_question_lingua"

        if follow_up:
            last_user = cls._find_last_message(history, "user")
            if last_user:
                previous_language, previous_confidence = cls._detect_question_language(
                    last_user
                )
                if previous_confidence in {"high", "medium"}:
                    return (
                        previous_language,
                        previous_confidence,
                        "history_last_user_lingua",
                    )

        return detected_language, confidence, "current_question_fallback"

    @staticmethod
    def _detect_with_lingua(question: str) -> tuple[str, str] | None:
        compact_question = " ".join(question.strip().split())
        if not compact_question:
            return None

        detected_language = _LINGUA_DETECTOR.detect_language_of(compact_question)
        if detected_language is None:
            return None

        confidence_values = _LINGUA_DETECTOR.compute_language_confidence_values(
            compact_question
        )
        top_confidence = float(confidence_values[0].value) if confidence_values else 0.0
        language_name = _LINGUA_LANGUAGE_NAMES.get(detected_language)
        if not language_name:
            return None

        if top_confidence >= 0.9:
            confidence = "high"
        elif top_confidence >= 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        return language_name, confidence

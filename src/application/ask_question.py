from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from lingua import Language, LanguageDetectorBuilder

from src.domain.dto.answer_result import AnswerResult, SourceResult
from src.domain.dto.retrieval_result import RetrievedChunk
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.query_rewrite_port import QueryRewritePort
from src.domain.services.retriever import RetrieverService
from src.shared.config import (
    LLM_CHUNK_MAX_CHARS,
    LLM_CONTEXT_CHARS_BUDGET,
    LLM_CONTEXT_MAX_CHUNKS,
    LLM_CONTEXT_RETRY_MAX_CHUNKS,
    RERANK_TOP_K,
    RAG_RETRIEVAL_TOP_K,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from src.shared.history_utils import find_last_message, is_context_dependent_question
from src.shared.logging_utils import log_event, perf_fields, take_perf_snapshot

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
_QUESTION_INTENT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "comparison": (
        re.compile(r"\b(compare|comparar|comparacao|comparison)\b"),
        re.compile(r"\b(diferenca|distincao|distinction|difference)\b"),
        re.compile(r"\b(versus|vs\.?)\b"),
        re.compile(r"\bentre\b.+\be\b"),
    ),
    "methodology": (
        re.compile(r"\b(metodologia|metodo|metodos|methodology|methods?)\b"),
        re.compile(r"\b(materials? and methods?|materiais e metodos)\b"),
        re.compile(r"\b(experimento|experimental|delineamento|amostra|sample)\b"),
        re.compile(r"\b(mediu|medir|medida|measurement|measured|avaliou)\b"),
        re.compile(r"\bcomo foi feito\b"),
    ),
    "results": (
        re.compile(r"\b(resultado|resultados|results?|findings?|achados)\b"),
        re.compile(r"\b(encontrou|observou|found|observed|efeito|impacto)\b"),
        re.compile(r"\b(conclusao|conclusoes|conclusion|conclusions)\b"),
        re.compile(r"\b(produtividade|yield|significancia|beneficios?)\b"),
    ),
    "definition": (
        re.compile(r"\b(o que e|o que sao|what is|what are|que es)\b"),
        re.compile(r"\b(defina|definir|define|definition|definicao)\b"),
        re.compile(r"\b(conceito|concepto|concept)\b"),
    ),
}
_INTENT_SECTION_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "definition": (
        re.compile(r"\b(abstract|resumo|resumen)\b"),
        re.compile(r"\b(introduction|introducao|introduccion|background)\b"),
        re.compile(r"\b(definition|definicao|conceito|concept)\b"),
    ),
    "methodology": (
        re.compile(r"\b(method|methods|metodo|metodos|metodologia)\b"),
        re.compile(r"\b(materials?|materiais|materiales)\b"),
        re.compile(r"\b(experiment|experimental|study design)\b"),
    ),
    "results": (
        re.compile(r"\b(results?|resultados?)\b"),
        re.compile(r"\b(discussion|discussao|discusion)\b"),
        re.compile(r"\b(conclusion|conclusions|conclusao|conclusoes)\b"),
    ),
    "comparison": (
        re.compile(r"\b(results?|resultados?)\b"),
        re.compile(r"\b(discussion|discussao|discusion)\b"),
        re.compile(r"\b(conclusion|conclusions|conclusao|conclusoes)\b"),
        re.compile(r"\b(abstract|resumo|resumen|introduction|introducao)\b"),
    ),
    "overview": (
        re.compile(r"\b(abstract|resumo|resumen)\b"),
        re.compile(r"\b(introduction|introducao|introduccion)\b"),
        re.compile(r"\b(discussion|discussao|discusion)\b"),
        re.compile(r"\b(conclusion|conclusions|conclusao|conclusoes)\b"),
    ),
}
_QUESTION_STOPWORDS = {
    "a",
    "about",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "defina",
    "do",
    "dos",
    "e",
    "el",
    "em",
    "en",
    "entre",
    "es",
    "foi",
    "for",
    "is",
    "la",
    "le",
    "les",
    "los",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "qual",
    "quais",
    "que",
    "sao",
    "the",
    "what",
    "with",
}
_QUESTION_GENERIC_TERMS = {
    "achados",
    "beneficios",
    "comparacao",
    "compare",
    "conclusoes",
    "diferenca",
    "efeito",
    "experimento",
    "impacto",
    "metodologia",
    "metodo",
    "paper",
    "resultado",
    "resultados",
    "study",
}
_INTENT_GUIDANCE: dict[str, str] = {
    "definition": (
        "Give a direct, friendly definition first. Then add scope, conditions, "
        "or caveats only when the sources support them. Avoid broad claims that "
        "go beyond the cited material."
    ),
    "methodology": (
        "Focus on how the study or practice was done: design, sample/context, "
        "variables, measurements, and limits. If the sources do not describe the "
        "method, say the retrieved sources do not provide enough methodological detail."
    ),
    "results": (
        "Separate findings from interpretation. Mention quantities, direction of "
        "effect, context, and uncertainty only when present in the sources. Do not "
        "infer statistical significance unless it is stated."
    ),
    "comparison": (
        "Compare only criteria supported by the sources. A short table is welcome "
        "when it makes the answer clearer. If one side lacks evidence, say that "
        "instead of forcing a balanced comparison."
    ),
    "overview": (
        "Give the most useful direct answer first, then summarize the evidence and "
        "important limitations. Keep the tone conversational and cite the supporting "
        "sources."
    ),
}
logger = logging.getLogger("agroecology.rag")


@dataclass(frozen=True)
class QuestionProfile:
    intent: str
    concepts: tuple[str, ...]
    max_context_chunks: int


@dataclass
class _ContextCandidate:
    chunk: RetrievedChunk
    rank: int
    estimated_chars: int
    priority: int
    concept_hits: tuple[str, ...]


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
        started_at = take_perf_snapshot()
        normalized_history: list[dict[str, Any]] = history or []
        follow_up = bool(normalized_history) and is_context_dependent_question(question)
        (
            expected_language,
            language_confidence,
            language_source,
        ) = self._resolve_answer_language(question, normalized_history, follow_up)
        requested_top_k = top_k or RERANK_TOP_K
        retrieval_top_k = self._resolve_retrieval_top_k()
        question_profile = self._profile_question(search_text=question)
        log_event(
            logger,
            logging.INFO,
            "rag_question_started",
            question_chars=len(question),
            top_k=requested_top_k,
            retrieval_top_k=retrieval_top_k,
            question_intent=question_profile.intent,
            question_concepts=len(question_profile.concepts),
            history_messages=len(normalized_history),
            follow_up_detected=follow_up,
            expected_language=expected_language,
            language_confidence=language_confidence,
            language_source=language_source,
        )
        search_query = question
        rewrite_started_at = take_perf_snapshot()
        if self._query_rewriter and normalized_history:
            search_query = self._query_rewriter.rewrite(question, normalized_history)
        rewrite_metrics = perf_fields(rewrite_started_at, "rewrite")
        retrieved = self._retriever.hybrid_search(
            search_query,
            top_k=retrieval_top_k,
        )

        # Enrich chunks with document metadata from title_map
        if title_map:
            for chunk in retrieved:
                doc_title = title_map.get(chunk.source)
                if doc_title:
                    chunk.title = doc_title

        answer_history: list[dict[str, Any]] = normalized_history if follow_up else []
        context_started_at = take_perf_snapshot()
        context_chunks = self._select_context_chunks(retrieved, question_profile)
        log_event(
            logger,
            logging.INFO,
            "rag_context_selected",
            retrieved_count=len(retrieved),
            selected_count=len(context_chunks),
            selected_chars=sum(len(chunk.text) for chunk in context_chunks),
            history_messages=len(answer_history),
            retrieval_top_k=retrieval_top_k,
            question_intent=question_profile.intent,
            question_concepts=len(question_profile.concepts),
            context_chunk_limit=question_profile.max_context_chunks,
            **perf_fields(context_started_at, "context_select"),
        )
        answer_started_at = take_perf_snapshot()
        answer = self._generate_answer(
            question,
            context_chunks,
            answer_history,
            expected_language,
            question_profile,
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
                question_profile,
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
            requested_top_k=requested_top_k,
            retrieval_top_k=retrieval_top_k,
            search_query_rewritten=search_query != question,
            expected_language=expected_language,
            language_confidence=language_confidence,
            language_source=language_source,
            **rewrite_metrics,
            **perf_fields(answer_started_at, "answer"),
            **perf_fields(started_at, "total"),
        )
        return AnswerResult(answer=answer, sources=sources)

    @staticmethod
    def _resolve_retrieval_top_k() -> int:
        return max(RAG_RETRIEVAL_TOP_K, RERANK_TOP_K, LLM_CONTEXT_MAX_CHUNKS)

    @classmethod
    def _build_context(cls, retrieved: list[RetrievedChunk]) -> str:
        parts = []
        for i, chunk in enumerate(retrieved, 1):
            source = chunk.source or "unknown"
            source_name = source.rsplit("/", 1)[-1]
            text = chunk.text.strip()

            attrs = [f'id="{i}"']
            if chunk.title:
                attrs.append(f'title="{cls._escape_context_attr(chunk.title)}"')
            if chunk.authors:
                attrs.append(f'authors="{cls._escape_context_attr(chunk.authors)}"')
            if chunk.year:
                attrs.append(f'year="{chunk.year}"')
            if chunk.doi:
                attrs.append(f'doi="{cls._escape_context_attr(chunk.doi)}"')
            if chunk.journal:
                attrs.append(f'journal="{cls._escape_context_attr(chunk.journal)}"')
            if chunk.section_title:
                attrs.append(
                    f'section="{cls._escape_context_attr(chunk.section_title)}"'
                )

            pages = cls._format_pages(chunk.page_start, chunk.page_end)
            if pages:
                attrs.append(f'pages="{pages}"')
            elif not chunk.title:
                attrs.append(f'source="{cls._escape_context_attr(source_name)}"')

            lines = [f"<source {' '.join(attrs)}>", text, "</source>"]
            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    @staticmethod
    def _escape_context_attr(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _format_pages(page_start: int | None, page_end: int | None) -> str:
        if page_start and page_end and page_start != page_end:
            return f"{page_start}-{page_end}"
        if page_start:
            return str(page_start)
        return ""

    def _generate_answer(
        self,
        question: str,
        context_chunks: list[RetrievedChunk],
        answer_history: list[dict[str, Any]],
        expected_language: str,
        question_profile: QuestionProfile,
    ) -> str:
        context = self._build_context(context_chunks)
        user_prompt = USER_PROMPT.replace("{context}", context)
        user_prompt = user_prompt.replace("{question}", question)
        user_prompt = user_prompt.replace("{expected_language}", expected_language)
        user_prompt = user_prompt.replace(
            "{intent_guidance}",
            _INTENT_GUIDANCE.get(
                question_profile.intent,
                _INTENT_GUIDANCE["overview"],
            ),
        )
        if answer_history:
            user_prompt = (
                "FOLLOW-UP QUESTION. Use the conversation history only to understand "
                "what the user is asking next and to avoid unnecessary repetition. "
                "Do not treat conversation history as factual evidence; factual "
                "support must come from the supplied sources below.\n\n" + user_prompt
            )
        return self._llm.complete(
            SYSTEM_PROMPT,
            user_prompt,
            history=answer_history,
        )

    @classmethod
    def _profile_question(cls, search_text: str) -> QuestionProfile:
        normalized = cls._normalize_for_matching(search_text)
        intent = cls._detect_question_intent(normalized)
        concepts = cls._extract_question_concepts(normalized)
        return QuestionProfile(
            intent=intent,
            concepts=concepts,
            max_context_chunks=cls._context_chunk_limit(intent, concepts),
        )

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.lower())
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        normalized = re.sub(r"[^\w\s.-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _detect_question_intent(normalized_question: str) -> str:
        for intent, patterns in _QUESTION_INTENT_PATTERNS.items():
            if any(pattern.search(normalized_question) for pattern in patterns):
                return intent
        return "overview"

    @staticmethod
    def _extract_question_concepts(normalized_question: str) -> tuple[str, ...]:
        cleaned = re.sub(
            r"\b(o que e|o que sao|what is|what are|que es|qual a diferenca entre|"
            r"qual e a diferenca entre|compare|comparar|defina|definir|em termos de)\b",
            " ",
            normalized_question,
        )
        phrases = re.split(r"\b(?:versus|vs\.?|entre|com|e|and|y)\b|[,;:/]", cleaned)
        concepts: list[str] = []

        for phrase in phrases:
            words = [
                word
                for word in phrase.split()
                if (
                    len(word) >= 4
                    and word not in _QUESTION_STOPWORDS
                    and word not in _QUESTION_GENERIC_TERMS
                    and not word.isdigit()
                )
            ]
            if not words:
                continue
            concept = " ".join(words[:3])
            if concept not in concepts:
                concepts.append(concept)
            if len(concepts) >= 5:
                break

        return tuple(concepts)

    @staticmethod
    def _context_chunk_limit(intent: str, concepts: tuple[str, ...]) -> int:
        if intent == "comparison" and len(concepts) >= 2:
            desired = 6
        else:
            desired = 4
        return max(1, min(LLM_CONTEXT_MAX_CHUNKS, desired))

    @classmethod
    def _select_context_chunks(
        cls, retrieved: list[RetrievedChunk], profile: QuestionProfile
    ) -> list[RetrievedChunk]:
        candidates = cls._prepare_context_candidates(retrieved, profile)
        if not candidates:
            return retrieved[:1]

        selected: list[_ContextCandidate] = []
        used_chars = 0
        selected_ids: set[str] = set()

        def add_candidate(candidate: _ContextCandidate) -> bool:
            nonlocal used_chars
            if candidate.chunk.id in selected_ids:
                return False
            if len(selected) >= profile.max_context_chunks:
                return False
            if (
                selected
                and used_chars + candidate.estimated_chars > LLM_CONTEXT_CHARS_BUDGET
            ):
                return False
            selected.append(candidate)
            selected_ids.add(candidate.chunk.id)
            used_chars += candidate.estimated_chars
            return True

        ranked_by_context = sorted(candidates, key=lambda c: (-c.priority, c.rank))
        ranked_by_relevance = sorted(candidates, key=lambda c: c.rank)

        if profile.intent == "comparison" and profile.concepts:
            for concept in profile.concepts:
                for candidate in ranked_by_context:
                    if concept in candidate.concept_hits and add_candidate(candidate):
                        break

            for candidate in ranked_by_context:
                if cls._adds_context_diversity(candidate, selected):
                    add_candidate(candidate)

        elif profile.intent in {"definition", "methodology", "results"}:
            for candidate in ranked_by_context:
                if candidate.priority > 0:
                    add_candidate(candidate)

        else:
            for candidate in ranked_by_relevance:
                if cls._adds_context_diversity(candidate, selected):
                    add_candidate(candidate)

        for candidate in ranked_by_relevance:
            add_candidate(candidate)

        return [candidate.chunk for candidate in selected] or [candidates[0].chunk]

    @classmethod
    def _prepare_context_candidates(
        cls, retrieved: list[RetrievedChunk], profile: QuestionProfile
    ) -> list[_ContextCandidate]:
        candidates: list[_ContextCandidate] = []

        for rank, chunk in enumerate(retrieved, 1):
            trimmed_text = chunk.text.strip()[:LLM_CHUNK_MAX_CHARS].strip()
            if not trimmed_text:
                continue

            chunk_copy = RetrievedChunk.from_dict(chunk.to_dict())
            chunk_copy.text = trimmed_text
            concept_hits = cls._matching_concepts(profile.concepts, chunk_copy)
            candidates.append(
                _ContextCandidate(
                    chunk=chunk_copy,
                    rank=rank,
                    estimated_chars=len(trimmed_text) + 300,
                    priority=cls._context_priority(chunk_copy, profile, concept_hits),
                    concept_hits=concept_hits,
                )
            )

        return candidates

    @classmethod
    def _context_priority(
        cls,
        chunk: RetrievedChunk,
        profile: QuestionProfile,
        concept_hits: tuple[str, ...],
    ) -> int:
        priority = len(concept_hits) * 20

        if cls._section_matches_intent(chunk.section_title, profile.intent):
            priority += 80

        block_types = {item.strip() for item in chunk.block_types.split(",")}
        if profile.intent == "definition" and "abstract" in block_types:
            priority += 30
        if profile.intent == "results" and "table" in block_types:
            priority += 20
        if (
            profile.intent in {"results", "comparison"}
            and "figure_caption" in block_types
        ):
            priority += 10

        chunk_text = cls._normalize_for_matching(chunk.text[:1200])
        if any(
            pattern.search(chunk_text)
            for pattern in _QUESTION_INTENT_PATTERNS.get(profile.intent, ())
        ):
            priority += 10

        return priority

    @classmethod
    def _matching_concepts(
        cls, concepts: tuple[str, ...], chunk: RetrievedChunk
    ) -> tuple[str, ...]:
        if not concepts:
            return ()

        searchable = cls._normalize_for_matching(
            " ".join(
                (
                    chunk.title,
                    chunk.section_title,
                    chunk.block_types,
                    chunk.text[:1600],
                )
            )
        )
        matches = [concept for concept in concepts if concept in searchable]
        return tuple(matches)

    @staticmethod
    def _section_matches_intent(section_title: str, intent: str) -> bool:
        if not section_title:
            return False
        normalized_section = AskQuestion._normalize_for_matching(section_title)
        return any(
            pattern.search(normalized_section)
            for pattern in _INTENT_SECTION_PATTERNS.get(intent, ())
        )

    @staticmethod
    def _adds_context_diversity(
        candidate: _ContextCandidate, selected: list[_ContextCandidate]
    ) -> bool:
        if not selected:
            return True

        candidate_doc = candidate.chunk.document_id or candidate.chunk.source
        candidate_section = candidate.chunk.section_title
        selected_docs = {
            item.chunk.document_id or item.chunk.source for item in selected
        }
        selected_sections = {item.chunk.section_title for item in selected}
        return (
            candidate_doc not in selected_docs
            or candidate_section not in selected_sections
        )

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
            last_user = find_last_message(history, "user")
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

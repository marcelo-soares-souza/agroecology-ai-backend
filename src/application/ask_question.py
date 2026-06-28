from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from lingua import Language, LanguageDetectorBuilder

from src.application.config import RagConfig
from src.domain.dto.answer_result import AnswerResult, SourceResult
from src.domain.dto.chat_message import ChatMessage
from src.domain.dto.document_metadata import DocumentMetadataMap
from src.domain.dto.retrieval_result import RetrievedChunk
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.query_rewrite_port import QueryRewritePort
from src.domain.services.conversation_history import (
    find_last_message,
    is_context_dependent_question,
)
from src.domain.services.retriever import RetrieverService
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
_CITATION_RE = re.compile(r"\[(\d+)\]")
_INSUFFICIENT_EVIDENCE_PATTERNS = (
    re.compile(r"\b(insufficient|not enough|do(?:es)? not provide|cannot determine)\b"),
    re.compile(r"\b(n[aã]o h[aá]|insuficiente|fontes? n[aã]o|contexto n[aã]o)\b"),
    re.compile(r"\b(no hay suficiente|no permite determinar|las fuentes no)\b"),
    re.compile(r"\b(pas assez|ne permet pas|les sources ne)\b"),
)
_CONCEPT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "sistemas agroflorestais": (
        "saf",
        "sistema agroflorestal",
        "sistemas agroflorestais",
        "agroforestry",
        "agroforestry system",
        "agroforestry systems",
    ),
    "agricultura organica": (
        "agricultura organica",
        "organic agriculture",
        "organic farming",
        "agricultura ecologica",
    ),
    "seguranca alimentar": (
        "seguranca alimentar",
        "soberania alimentar",
        "food security",
        "food sovereignty",
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

_ACADEMIC_AUTHORITY_CONTEXT_BONUS_MAX = 4
_ACADEMIC_AUTHORITY_CITATION_CAP = 500
_ACADEMIC_AUTHORITY_REFERENCE_CAP = 150


@dataclass(frozen=True)
class QuestionProfile:
    language: str
    is_follow_up: bool
    intent: str
    concepts: tuple[str, ...]
    requested_scope: str
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
        config: RagConfig,
        query_rewriter: QueryRewritePort | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._config = config
        self._query_rewriter = query_rewriter

    def execute(
        self,
        question: str,
        top_k: int | None = None,
        document_metadata_map: DocumentMetadataMap | None = None,
        history: Sequence[ChatMessage] | None = None,
    ) -> AnswerResult:
        started_at = take_perf_snapshot()
        normalized_history = list(history or [])
        follow_up = bool(normalized_history) and is_context_dependent_question(question)
        (
            expected_language,
            language_confidence,
            language_source,
        ) = self._resolve_answer_language(question, normalized_history, follow_up)
        requested_top_k = top_k or self._config.rerank_top_k
        retrieval_top_k = self._resolve_retrieval_top_k()
        question_profile = self._profile_question(
            search_text=question,
            language=expected_language,
            is_follow_up=follow_up,
        )
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

        self._apply_document_metadata(retrieved, document_metadata_map)

        answer_history: list[ChatMessage] = normalized_history if follow_up else []
        context_started_at = take_perf_snapshot()
        context_chunks = self._select_context_chunks(retrieved, question_profile)
        self._log_context_authority_scores(context_chunks)
        covered_concepts = self._covered_concepts(question_profile, context_chunks)
        missing_concept_count = max(
            0, len(question_profile.concepts) - len(covered_concepts)
        )
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
            covered_concepts=len(covered_concepts),
            missing_concepts=missing_concept_count,
            context_chunk_limit=question_profile.max_context_chunks,
            **perf_fields(context_started_at, "context_select"),
        )
        log_event(
            logger,
            logging.INFO,
            "rag_context_coverage",
            question_intent=question_profile.intent,
            question_concepts=len(question_profile.concepts),
            covered_concepts=len(covered_concepts),
            missing_concepts=missing_concept_count,
            selected_count=len(context_chunks),
            requested_scope=question_profile.requested_scope,
            follow_up=question_profile.is_follow_up,
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
            retry_chunks = context_chunks[: self._config.llm_context_retry_max_chunks]
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

        cited_source_ids: list[int] = []
        if answer.strip():
            answer, cited_source_ids = self._validate_answer_citations(
                answer=answer,
                question=question,
                context_chunks=context_chunks,
                answer_history=answer_history,
                expected_language=expected_language,
                question_profile=question_profile,
            )

        _normalize_scores(context_chunks)

        sources = self._build_source_results(context_chunks, cited_source_ids)

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
    def _apply_document_metadata(
        retrieved: list[RetrievedChunk],
        document_metadata_map: DocumentMetadataMap | None,
    ) -> None:
        if not document_metadata_map:
            return

        for chunk in retrieved:
            metadata = document_metadata_map.get(chunk.source)
            if not metadata:
                continue

            if metadata.title:
                chunk.title = metadata.title
            if metadata.authors:
                chunk.authors = metadata.authors
            if metadata.year:
                chunk.year = metadata.year
            if metadata.doi:
                chunk.doi = metadata.doi
            if metadata.journal:
                chunk.journal = metadata.journal
            if metadata.language:
                chunk.language = metadata.language
            if metadata.citation_count is not None:
                chunk.citation_count = metadata.citation_count
            if metadata.reference_count is not None:
                chunk.reference_count = metadata.reference_count

    @staticmethod
    def _build_source_results(
        context_chunks: list[RetrievedChunk],
        cited_source_ids: list[int],
    ) -> list[SourceResult]:
        sources: list[SourceResult] = []

        for citation_id in cited_source_ids:
            if citation_id < 1 or citation_id > len(context_chunks):
                continue

            chunk = context_chunks[citation_id - 1]
            source = chunk.source or "unknown"
            meta = {
                "source": source,
                "chunk_index": chunk.chunk_index,
                "search_type": chunk.search_type,
            }
            doc_id = chunk.document_id
            if not doc_id:
                source_name = source.rsplit("/", 1)[-1]
                doc_id = source_name.rsplit(".", 1)[0]
            if doc_id:
                meta["document_id"] = doc_id
            for field in (
                "title",
                "authors",
                "year",
                "doi",
                "journal",
                "language",
                "page_start",
                "page_end",
                "section_title",
                "block_types",
            ):
                val = getattr(chunk, field)
                if val:
                    meta[field] = val
            sources.append(
                SourceResult(
                    text=chunk.text[:300],
                    score=chunk.score,
                    score_type=chunk.score_type,
                    rank=citation_id,
                    metadata=meta,
                )
            )

        return sources

    def _resolve_retrieval_top_k(self) -> int:
        return max(
            self._config.rag_retrieval_top_k,
            self._config.rerank_top_k,
            self._config.llm_context_max_chunks,
        )

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
            if chunk.language:
                attrs.append(f'language="{cls._escape_context_attr(chunk.language)}"')
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
        answer_history: list[ChatMessage],
        expected_language: str,
        question_profile: QuestionProfile,
    ) -> str:
        context = self._build_context(context_chunks)
        user_prompt = self._config.user_prompt.replace("{context}", context)
        user_prompt = user_prompt.replace("{question}", question)
        user_prompt = user_prompt.replace("{expected_language}", expected_language)
        intent_guidance = _INTENT_GUIDANCE.get(
            question_profile.intent,
            _INTENT_GUIDANCE["overview"],
        )
        coverage_guidance = self._coverage_guidance(question_profile, context_chunks)
        if coverage_guidance:
            intent_guidance = f"{intent_guidance} {coverage_guidance}"
        user_prompt = user_prompt.replace(
            "{intent_guidance}",
            intent_guidance,
        )
        if answer_history:
            user_prompt = (
                "FOLLOW-UP QUESTION. Use the conversation history only to understand "
                "what the user is asking next and to avoid unnecessary repetition. "
                "Do not treat conversation history as factual evidence; factual "
                "support must come from the supplied sources below.\n\n" + user_prompt
            )
        return self._llm.complete(
            self._config.system_prompt,
            user_prompt,
            history=[message.to_dict() for message in answer_history],
        )

    @classmethod
    def _coverage_guidance(
        cls,
        profile: QuestionProfile,
        context_chunks: list[RetrievedChunk],
    ) -> str:
        if not profile.concepts:
            return ""
        covered = cls._covered_concepts(profile, context_chunks)
        if len(covered) >= len(profile.concepts):
            return ""
        return (
            "If any requested concept or comparison side is not directly supported "
            "by the supplied sources, state that limitation clearly instead of "
            "filling the gap from outside knowledge."
        )

    def _validate_answer_citations(
        self,
        answer: str,
        question: str,
        context_chunks: list[RetrievedChunk],
        answer_history: list[ChatMessage],
        expected_language: str,
        question_profile: QuestionProfile,
    ) -> tuple[str, list[int]]:
        valid_source_count = len(context_chunks)
        cited_source_ids = self._extract_citation_ids(answer)
        invalid_citation_count = self._invalid_citation_count(
            cited_source_ids,
            valid_source_count,
        )
        missing_citations = (
            valid_source_count > 0
            and not cited_source_ids
            and not self._declares_insufficient_evidence(answer)
        )
        repair_attempted = False

        if invalid_citation_count or missing_citations:
            repaired = self._repair_citations(
                answer=answer,
                question=question,
                context_chunks=context_chunks,
                answer_history=answer_history,
                expected_language=expected_language,
                question_profile=question_profile,
            )
            repair_attempted = bool(repaired)
            if repaired:
                answer = repaired
                cited_source_ids = self._extract_citation_ids(answer)
                invalid_citation_count = self._invalid_citation_count(
                    cited_source_ids,
                    valid_source_count,
                )

        if invalid_citation_count:
            answer = self._remove_invalid_citations(answer, valid_source_count)
            cited_source_ids = self._extract_citation_ids(answer)
            invalid_citation_count = self._invalid_citation_count(
                cited_source_ids,
                valid_source_count,
            )

        valid_citations = [
            citation_id
            for citation_id in cited_source_ids
            if 1 <= citation_id <= valid_source_count
        ]
        if not valid_citations and self._declares_insufficient_evidence(answer):
            valid_citations = []
        final_missing_citations = (
            valid_source_count > 0
            and not valid_citations
            and not self._declares_insufficient_evidence(answer)
        )

        log_event(
            logger,
            logging.INFO,
            "rag_citation_validation",
            selected_source_count=valid_source_count,
            cited_source_count=len(valid_citations),
            invalid_citation_count=invalid_citation_count,
            missing_citations=final_missing_citations,
            repair_attempted=repair_attempted,
            question_intent=question_profile.intent,
        )
        return answer, valid_citations

    def _repair_citations(
        self,
        answer: str,
        question: str,
        context_chunks: list[RetrievedChunk],
        answer_history: list[ChatMessage],
        expected_language: str,
        question_profile: QuestionProfile,
    ) -> str:
        if not context_chunks:
            return ""

        context = self._build_context(context_chunks)
        guidance = _INTENT_GUIDANCE.get(
            question_profile.intent,
            _INTENT_GUIDANCE["overview"],
        )
        repair_prompt = (
            f"MANDATORY OUTPUT LANGUAGE: {expected_language}\n"
            f"Answer only in {expected_language}.\n\n"
            "Correct only citation problems in the draft answer. Use only source "
            f"IDs [1] through [{len(context_chunks)}]. Do not add new factual claims. "
            "If a claim is not directly supported by the sources, remove it or say "
            "the supplied sources are insufficient. Return only the corrected "
            "answer, with no explanation of the correction.\n\n"
            f"Question-specific guidance:\n{guidance}\n\n"
            f"Current user question:\n{question}\n\n"
            f"Retrieved context:\n---\n{context}\n---\n\n"
            f"Draft answer:\n{answer}"
        )
        try:
            return self._llm.complete(
                self._config.system_prompt,
                repair_prompt,
                history=[message.to_dict() for message in answer_history],
            ).strip()
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "rag_citation_repair_failed",
                error=exc,
                selected_source_count=len(context_chunks),
            )
            return ""

    @staticmethod
    def _extract_citation_ids(answer: str) -> list[int]:
        citation_ids: list[int] = []
        for match in _CITATION_RE.finditer(answer):
            citation_id = int(match.group(1))
            if citation_id not in citation_ids:
                citation_ids.append(citation_id)
        return citation_ids

    @staticmethod
    def _invalid_citation_count(
        cited_source_ids: list[int],
        valid_source_count: int,
    ) -> int:
        return sum(
            1
            for citation_id in cited_source_ids
            if citation_id < 1 or citation_id > valid_source_count
        )

    @staticmethod
    def _remove_invalid_citations(answer: str, valid_source_count: int) -> str:
        def replacement(match: re.Match[str]) -> str:
            citation_id = int(match.group(1))
            if 1 <= citation_id <= valid_source_count:
                return match.group(0)
            return ""

        cleaned = _CITATION_RE.sub(replacement, answer)
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _declares_insufficient_evidence(answer: str) -> bool:
        normalized = AskQuestion._normalize_for_matching(answer)
        return any(
            pattern.search(normalized) for pattern in _INSUFFICIENT_EVIDENCE_PATTERNS
        )

    @classmethod
    def _profile_question(
        cls,
        search_text: str,
        language: str,
        is_follow_up: bool,
    ) -> QuestionProfile:
        normalized = cls._normalize_for_matching(search_text)
        intent = cls._detect_question_intent(normalized)
        concepts = cls._extract_question_concepts(normalized)
        requested_scope = cls._detect_requested_scope(normalized)
        return QuestionProfile(
            language=language,
            is_follow_up=is_follow_up,
            intent=intent,
            concepts=concepts,
            requested_scope=requested_scope,
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
            r"qual e a diferenca entre|compare|comparar|defina|definir|em termos de|"
            r"quais sao|quais os|what about|tell me about)\b",
            " ",
            normalized_question,
        )
        concepts: list[str] = []

        for canonical, terms in _CONCEPT_SYNONYMS.items():
            if any(term in cleaned for term in terms):
                concepts.append(canonical)

        phrases = re.split(
            r"\b(?:versus|vs\.?|entre|with|com|e|and|y|et|ou|or)\b|[,;:/]",
            cleaned,
        )
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
            concept = " ".join(words[:5])
            if concept not in concepts:
                concepts.append(concept)
            if len(concepts) >= 5:
                break

        return tuple(concepts)

    @staticmethod
    def _detect_requested_scope(normalized_question: str) -> str:
        if re.search(
            r"\b(este artigo|esse artigo|neste estudo|nesse estudo|this paper|"
            r"this study|el estudio|este estudio|cet article|cette etude)\b",
            normalized_question,
        ):
            return "single_study"
        if re.search(r"\b(compare|comparar|versus|vs\.?|entre)\b", normalized_question):
            return "comparison"
        return "general"

    @staticmethod
    def _context_chunk_limit(intent: str, concepts: tuple[str, ...]) -> int:
        if intent == "comparison" or len(concepts) >= 2:
            desired = min(6, max(4, len(concepts) * 2))
        else:
            desired = 4
        return max(1, desired)

    def _select_context_chunks(
        self, retrieved: list[RetrievedChunk], profile: QuestionProfile
    ) -> list[RetrievedChunk]:
        cls = type(self)
        candidates = self._prepare_context_candidates(retrieved, profile)
        if not candidates:
            return retrieved[:1]

        selected: list[_ContextCandidate] = []
        used_chars = 0
        selected_ids: set[str] = set()

        def add_candidate(candidate: _ContextCandidate) -> bool:
            nonlocal used_chars
            candidate_key = cls._candidate_key(candidate)
            if candidate_key in selected_ids:
                return False
            if len(selected) >= profile.max_context_chunks:
                return False
            if (
                selected
                and used_chars + candidate.estimated_chars
                > self._config.llm_context_chars_budget
            ):
                return False
            selected.append(candidate)
            selected_ids.add(candidate_key)
            used_chars += candidate.estimated_chars
            return True

        ranked_by_context = sorted(
            candidates,
            key=lambda c: (-c.priority, cls._authority_adjusted_rank(c)),
        )
        ranked_by_relevance = sorted(candidates, key=cls._authority_adjusted_rank)

        if profile.concepts and (
            profile.intent == "comparison" or len(profile.concepts) >= 2
        ):
            for concept in profile.concepts:
                for candidate in ranked_by_context:
                    if concept in candidate.concept_hits and add_candidate(candidate):
                        break

            for candidate in ranked_by_context:
                if cls._adds_context_diversity(candidate, selected):
                    add_candidate(candidate)

        elif profile.intent in {"definition", "methodology", "results"}:
            for candidate in ranked_by_context:
                if candidate.priority > 0 and add_candidate(candidate):
                    if (
                        profile.intent in {"methodology", "results"}
                        and profile.requested_scope == "single_study"
                    ):
                        for adjacent in cls._adjacent_candidates(
                            candidate,
                            ranked_by_relevance,
                        ):
                            add_candidate(adjacent)

        else:
            for candidate in ranked_by_relevance:
                if cls._adds_context_diversity(candidate, selected):
                    add_candidate(candidate)

        for candidate in ranked_by_relevance:
            add_candidate(candidate)

        return [candidate.chunk for candidate in selected] or [candidates[0].chunk]

    @staticmethod
    def _candidate_key(candidate: _ContextCandidate) -> str:
        chunk = candidate.chunk
        return chunk.id or f"{chunk.source}:{chunk.chunk_index}"

    @classmethod
    def _adjacent_candidates(
        cls,
        base: _ContextCandidate,
        candidates: list[_ContextCandidate],
    ) -> list[_ContextCandidate]:
        base_chunk = base.chunk
        adjacent = [
            candidate
            for candidate in candidates
            if (
                cls._candidate_key(candidate) != cls._candidate_key(base)
                and candidate.chunk.source == base_chunk.source
                and abs(candidate.chunk.chunk_index - base_chunk.chunk_index) == 1
            )
        ]
        return sorted(adjacent, key=lambda candidate: candidate.rank)

    def _prepare_context_candidates(
        self, retrieved: list[RetrievedChunk], profile: QuestionProfile
    ) -> list[_ContextCandidate]:
        cls = type(self)
        candidates: list[_ContextCandidate] = []

        for rank, chunk in enumerate(retrieved, 1):
            trimmed_text = self._prepare_context_text(chunk)
            if not trimmed_text:
                continue

            chunk_copy = RetrievedChunk.from_dict(chunk.to_dict())
            chunk_copy.text = trimmed_text
            concept_hits = cls._matching_concepts(profile.concepts, chunk_copy)
            authority_score = cls._academic_authority_score(chunk_copy)
            authority_bonus = cls._academic_authority_bonus(authority_score)
            chunk_copy.academic_authority_score = authority_score
            chunk_copy.academic_authority_bonus = authority_bonus
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

    def _prepare_context_text(self, chunk: RetrievedChunk) -> str:
        text = chunk.text.strip()
        limit = self._config.llm_chunk_max_chars
        if len(text) <= limit:
            return text

        log_event(
            logger,
            logging.WARNING,
            "rag_legacy_chunk_truncated",
            chunk_id=chunk.id,
            source=chunk.source,
            chunk_index=chunk.chunk_index,
            text_chars=len(text),
            limit_chars=limit,
        )
        split_at = text.rfind(" ", 0, limit)
        if split_at < int(limit * 0.6):
            split_at = limit
        return text[:split_at].strip()

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

    @staticmethod
    def _academic_authority_score(chunk: RetrievedChunk) -> float:
        citation_count = chunk.citation_count
        reference_count = chunk.reference_count
        if citation_count is None and reference_count is None:
            return 0.0

        citation_score = 0.0
        reference_score = 0.0

        if citation_count is not None:
            citation_score = min(
                1.0,
                math.log1p(max(0, citation_count))
                / math.log1p(_ACADEMIC_AUTHORITY_CITATION_CAP),
            )

        if reference_count is not None:
            reference_score = min(
                1.0,
                math.log1p(max(0, reference_count))
                / math.log1p(_ACADEMIC_AUTHORITY_REFERENCE_CAP),
            )

        if citation_count is not None and reference_count is not None:
            score = (citation_score * 0.8) + (reference_score * 0.2)
        elif citation_count is not None:
            score = citation_score
        else:
            score = reference_score * 0.35

        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def _academic_authority_bonus(authority_score: float) -> int:
        return round(
            max(0.0, min(1.0, authority_score))
            * _ACADEMIC_AUTHORITY_CONTEXT_BONUS_MAX
        )

    @staticmethod
    def _authority_adjusted_rank(candidate: _ContextCandidate) -> int:
        return max(1, candidate.rank - candidate.chunk.academic_authority_bonus)

    @staticmethod
    def _log_context_authority_scores(context_chunks: list[RetrievedChunk]) -> None:
        for rank, chunk in enumerate(context_chunks, 1):
            log_event(
                logger,
                logging.INFO,
                "rag_context_authority_score",
                context_rank=rank,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                source=chunk.source,
                authority_score=chunk.academic_authority_score,
                authority_bonus=chunk.academic_authority_bonus,
                citation_count=chunk.citation_count,
                reference_count=chunk.reference_count,
            )

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
        matches = [
            concept
            for concept in concepts
            if any(term in searchable for term in cls._concept_terms(concept))
        ]
        return tuple(matches)

    @staticmethod
    def _concept_terms(concept: str) -> tuple[str, ...]:
        terms = _CONCEPT_SYNONYMS.get(concept, ())
        return (concept, *terms)

    @classmethod
    def _covered_concepts(
        cls,
        profile: QuestionProfile,
        chunks: list[RetrievedChunk],
    ) -> tuple[str, ...]:
        covered: list[str] = []
        for chunk in chunks:
            for concept in cls._matching_concepts(profile.concepts, chunk):
                if concept not in covered:
                    covered.append(concept)
        return tuple(covered)

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
        history: Sequence[ChatMessage],
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

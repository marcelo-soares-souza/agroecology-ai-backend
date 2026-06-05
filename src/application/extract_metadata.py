from __future__ import annotations

import json
import logging
import re

from src.domain.ports.llm_port import LLMPort
from src.shared.logging_utils import log_event

_DOI_PATTERN = re.compile(r"\b(10\.\d{4,}/[^\s]+)\b")
_YEAR_PATTERN = re.compile(r"\b(19[7-9]\d|20[0-2]\d)\b")
_LANGUAGE_PATTERNS = {
    "pt": re.compile(
        r"\b(da|do|das|dos|no|na|nos|nas|uma|com|para|como|entre|sobre|mais|pelo|pela|pelos|pelas)\b",
        re.IGNORECASE,
    ),
    "es": re.compile(
        r"\b(del|las|los|una|como|para|entre|sobre|más|por|con|muy)\b",
        re.IGNORECASE,
    ),
    "en": re.compile(
        r"\b(the|and|for|with|from|this|that|between|about|more|have|been)\b",
        re.IGNORECASE,
    ),
}

_EXTRACT_PROMPT = """You are a document metadata extractor. Given the first pages of an academic article, research paper, or document, extract:

1. The document title
2. The author(s)
3. The journal or publication name (if identifiable)
4. The abstract text (first 500 chars)
5. Keywords (as comma-separated list)
6. Language of the document (ISO 639-1 code: "pt", "en", "es", etc.)

Rules:
- Return ONLY valid JSON, like: {"title": "The Title", "authors": "Author One, Author Two", "journal": "Journal Name", "abstract": "...", "keywords": "kw1, kw2", "language": "en"}
- If you cannot identify a field, set it to an empty string.
- Do NOT include any explanation, markdown, or extra text — ONLY the JSON object.
- Authors should be separated by commas if there are multiple.

Text:
---
{text}
---

JSON:"""

logger = logging.getLogger("agroecology.metadata")


def _heuristic_extract(text: str) -> dict:
    result: dict = {"doi": "", "year": None}

    doi_match = _DOI_PATTERN.search(text)
    if doi_match:
        result["doi"] = doi_match.group(1)

    year_matches = _YEAR_PATTERN.findall(text)
    if year_matches:
        years = [int(y) for y in year_matches if 1975 <= int(y) <= 2026]
        if years:
            result["year"] = max(years)

    return result


def _detect_language(text: str) -> str:
    scores: dict[str, int] = {}
    for lang, pattern in _LANGUAGE_PATTERNS.items():
        scores[lang] = len(pattern.findall(text.lower()))
    if scores:
        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 3:
            return best
    return ""


class ExtractMetadata:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def execute(self, first_page_text: str) -> dict[str, str]:
        text = first_page_text.strip()
        if not text or len(text) < 50:
            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_skipped",
                reason="insufficient_text",
                text_chars=len(text),
            )
            return {
                "title": "",
                "authors": "",
                "doi": "",
                "year": "",
                "journal": "",
                "abstract": "",
                "keywords": "",
                "language": "",
            }

        truncated = text[:6000]

        # Heuristic extraction (no LLM cost)
        heuristics = _heuristic_extract(truncated)
        detected_lang = _detect_language(truncated)

        try:
            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_started",
                text_chars=len(truncated),
            )
            raw = self._llm.complete(
                system_prompt="Return only valid JSON.",
                user_prompt=_EXTRACT_PROMPT.format(text=truncated),
                temperature=0.0,
                max_tokens=4096,
            )

            cleaned = raw.strip()
            if cleaned.startswith("```"):
                idx = cleaned.find("\n")
                if idx != -1:
                    cleaned = cleaned[idx + 1 :]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            result = json.loads(cleaned.strip())
            extracted = {
                "title": str(result.get("title", "") or "").strip(),
                "authors": str(result.get("authors", "") or "").strip(),
                "journal": str(result.get("journal", "") or "").strip(),
                "abstract": str(result.get("abstract", "") or "")[:500].strip(),
                "keywords": str(result.get("keywords", "") or "").strip(),
                "language": str(
                    result.get("language", "") or detected_lang or ""
                ).strip(),
            }
            # Heuristics override LLM when confident
            if heuristics["doi"]:
                extracted["doi"] = heuristics["doi"]
            extracted["year"] = str(heuristics["year"]) if heuristics["year"] else ""
            if not extracted["language"] and detected_lang:
                extracted["language"] = detected_lang

            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_completed",
                has_title=bool(extracted["title"]),
                has_authors=bool(extracted["authors"]),
                has_doi=bool(extracted["doi"]),
                has_year=bool(extracted["year"]),
            )
            return extracted
        except Exception:
            log_event(logger, logging.ERROR, "metadata_extraction_failed")
            return {
                "title": "",
                "authors": "",
                "doi": heuristics.get("doi", ""),
                "year": str(heuristics.get("year", ""))
                if heuristics.get("year")
                else "",
                "journal": "",
                "abstract": "",
                "keywords": "",
                "language": detected_lang,
            }

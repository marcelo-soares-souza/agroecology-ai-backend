from __future__ import annotations

import json
import logging

from src.domain.dto.document_result import MetadataResult
from src.domain.ports.llm_port import LLMPort
from src.shared.logging_utils import log_event

_EXTRACT_PROMPT = """You are a document metadata extractor. Given the first pages of an academic article or research paper, extract:

1. The document title
2. The author(s)

Rules:
- Return ONLY valid JSON, like: {"title": "The Title", "authors": "Author One, Author Two"}
- If you cannot identify a field, set it to an empty string.
- Do NOT include any explanation, markdown, or extra text — ONLY the JSON object.
- Authors should be separated by commas if there are multiple.

Text:
---
{text}
---

JSON:"""

logger = logging.getLogger("agroecology.metadata")


class ExtractMetadata:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def execute(self, first_page_text: str) -> MetadataResult:
        text = first_page_text.strip()
        if not text or len(text) < 50:
            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_skipped",
                reason="insufficient_text",
                text_chars=len(text),
            )
            return MetadataResult(title="", authors="")

        truncated = text[:6000]

        try:
            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_started",
                text_chars=len(truncated),
            )
            raw = self._llm.complete(
                system_prompt="Return only valid JSON.",
                user_prompt=_EXTRACT_PROMPT.replace("{text}", truncated),
                temperature=0.0,
                max_tokens=1024,
            )

            cleaned = raw.strip()
            log_event(
                logger,
                logging.DEBUG,
                "metadata_llm_raw_response",
                response_len=len(cleaned),
                response_preview=cleaned[:200],
            )
            if not cleaned:
                log_event(
                    logger,
                    logging.ERROR,
                    "metadata_llm_empty_response",
                )
                return MetadataResult(title="", authors="")
            if cleaned.startswith("```"):
                idx = cleaned.find("\n")
                if idx != -1:
                    cleaned = cleaned[idx + 1 :]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            result = json.loads(cleaned.strip())
            extracted = MetadataResult(
                title=str(result.get("title", "") or "").strip(),
                authors=str(result.get("authors", "") or "").strip(),
            )

            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_completed",
                has_title=bool(extracted.title),
                has_authors=bool(extracted.authors),
            )
            return extracted
        except json.JSONDecodeError as exc:
            log_event(
                logger,
                logging.ERROR,
                "metadata_json_parse_failed",
                error=str(exc),
                raw_preview=cleaned[:300] if "cleaned" in dir() else "",
            )
            return MetadataResult(title="", authors="")
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "metadata_extraction_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return MetadataResult(title="", authors="")

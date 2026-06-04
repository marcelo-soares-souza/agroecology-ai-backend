from __future__ import annotations

import logging

from src.domain.ports.llm_port import LLMPort
from src.shared.logging_utils import log_event

_EXTRACT_PROMPT = """You are a document metadata extractor. Given the first pages of an academic article, research paper, or document, extract:

1. The document title
2. The author(s)

Rules:
- Return ONLY valid JSON, like: {{"title": "The Title", "authors": "Author One, Author Two"}}
- If you cannot identify the title, set it to an empty string.
- If you cannot identify the authors, set them to an empty string.
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
            return {"title": "", "authors": ""}

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
                user_prompt=_EXTRACT_PROMPT.format(text=truncated),
                temperature=0.0,
                max_tokens=4096,
            )

            import json

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
            }
            log_event(
                logger,
                logging.INFO,
                "metadata_extraction_completed",
                has_title=bool(extracted["title"]),
                has_authors=bool(extracted["authors"]),
            )
            return extracted
        except Exception:
            log_event(logger, logging.ERROR, "metadata_extraction_failed")
            return {"title": "", "authors": ""}

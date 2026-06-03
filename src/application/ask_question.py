from __future__ import annotations

from src.domain.ports.document_repository import DocumentRepository
from src.domain.ports.llm_port import LLMPort
from src.domain.services.retriever import RetrieverService
from src.shared.config import HYBRID_TOP_K, SYSTEM_PROMPT, USER_PROMPT


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
    ) -> dict:
        retrieved = self._retriever.hybrid_search(
            question,
            top_k=top_k or HYBRID_TOP_K,
        )

        context = self._build_context(retrieved)
        answer = self._llm.complete(
            SYSTEM_PROMPT,
            USER_PROMPT.format(context=context, question=question),
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

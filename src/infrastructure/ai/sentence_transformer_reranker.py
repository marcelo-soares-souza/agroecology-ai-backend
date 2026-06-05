from __future__ import annotations

import logging

import torch
from sentence_transformers import CrossEncoder

from src.domain.ports.reranker_port import RerankerPort

logger = logging.getLogger(__name__)


class SentenceTransformerReranker(RerankerPort):
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        self._model_name = model_name
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            device = "cpu"
        logger.info("Reranker using device: %s", device)
        self._device = torch.device(device)
        self._model: CrossEncoder | None = None

    def _load_model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(
                self._model_name,
                device=self._device,
            )
            if self._model.model is not None:
                self._model.model.to(self._device)  # type: ignore[arg-type,union-attr]
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int) -> list[dict]:
        if not documents:
            return []

        model = self._load_model()
        pairs = [(query, str(doc["text"])) for doc in documents]
        scores = model.predict(pairs)  # type: ignore[arg-type]

        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_k]:
            doc = dict(documents[idx])
            doc["_distance"] = float(score)
            doc["_search_type"] = "rerank"
            doc["_rerank_score"] = float(score)
            results.append(doc)
        return results

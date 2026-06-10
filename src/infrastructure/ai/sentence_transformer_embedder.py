from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import torch
from sentence_transformers import SentenceTransformer

from src.domain.ports.embedding_port import EmbeddingPort

logger = logging.getLogger("agroecology.embedding")


@contextmanager
def _suppress_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)


class SentenceTransformerEmbedder(EmbeddingPort):
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            device = "cpu"
        logger.info("Embedder using device: %s", device)
        self._device = torch.device(device)
        with _suppress_stderr():
            self._model = SentenceTransformer(model_name, device=self._device)
        self._dim = self._model.get_embedding_dimension()
        assert self._dim is not None

    def close(self) -> None:
        pass

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        embedding = self._model.encode([query], normalize_embeddings=True)
        return embedding[0].tolist()

    def get_dimension(self) -> int:
        return self._dim

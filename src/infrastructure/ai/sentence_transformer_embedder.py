from __future__ import annotations

import os
from contextlib import contextmanager

from sentence_transformers import SentenceTransformer

from src.domain.ports.embedding_port import EmbeddingPort


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
    def __init__(self, model_name: str) -> None:
        with _suppress_stderr():
            self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_embedding_dimension()
        assert self._dim is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        embedding = self._model.encode([query], normalize_embeddings=True)
        return embedding[0].tolist()

    def get_dimension(self) -> int:
        return self._dim

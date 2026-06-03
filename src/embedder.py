from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from contextlib import contextmanager

from .config import (
    EMBEDDING_BACKEND,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)


# ── suppress noisy stderr from sentence-transformers ──────────────────────


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


# ── abstract backend ──────────────────────────────────────────────────────


class EmbedderBackend(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]: ...

    @abstractmethod
    def get_dimension(self) -> int: ...


# ── SentenceTransformer backend (local model) ─────────────────────────────

_ST_BACKEND: SentenceTransformerBackend | None = None


class SentenceTransformerBackend(EmbedderBackend):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        with _suppress_stderr():
            self._model = SentenceTransformer(model_name)
        self._dim = self._model.get_embedding_dimension()
        assert self._dim is not None
        logger.info("SentenceTransformer loaded: %s (%d-dim)", model_name, self._dim)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        embedding = self._model.encode([query], normalize_embeddings=True)
        return embedding[0].tolist()

    def get_dimension(self) -> int:
        return self._dim


# ── Ollama backend (HTTP API) ─────────────────────────────────────────────

_OLLAMA_BACKEND: OllamaBackend | None = None


class OllamaBackend(EmbedderBackend):
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dim: int | None = None
        logger.info("Ollama backend configured: %s (model: %s)", base_url, model)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        try:
            resp = httpx.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Ollama embedding failed: {e}") from e

        embeddings = data.get("embeddings", [])
        if not embeddings:
            raise RuntimeError("Ollama returned empty embeddings")

        if self._dim is None:
            self._dim = len(embeddings[0])
            logger.info("Ollama embedding dimension detected: %d", self._dim)

        return embeddings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, query: str) -> list[float]:
        return self._embed([query])[0]

    def get_dimension(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed_query("dimension probe"))
        return self._dim


# ── public API (unchanged interface) ──────────────────────────────────────


def get_embedder() -> EmbedderBackend:
    global _ST_BACKEND, _OLLAMA_BACKEND

    if EMBEDDING_BACKEND == "ollama":
        if _OLLAMA_BACKEND is None:
            _OLLAMA_BACKEND = OllamaBackend(OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL)
        return _OLLAMA_BACKEND

    if _ST_BACKEND is None:
        _ST_BACKEND = SentenceTransformerBackend(EMBEDDING_MODEL)
    return _ST_BACKEND


def get_embedding_dim() -> int:
    return get_embedder().get_dimension()


def embed_texts(texts: list[str]) -> list[list[float]]:
    return get_embedder().embed_texts(texts)


def embed_query(query: str) -> list[float]:
    return get_embedder().embed_query(query)

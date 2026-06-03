import os
import sys
from contextlib import contextmanager

from .config import EMBEDDING_MODEL


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


from sentence_transformers import SentenceTransformer

_embedder: SentenceTransformer | None = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        with _suppress_stderr():
            _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def get_embedding_dim() -> int:
    return get_embedder().get_embedding_dimension()


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedder()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    model = get_embedder()
    embedding = model.encode([query], normalize_embeddings=True)
    return embedding[0].tolist()

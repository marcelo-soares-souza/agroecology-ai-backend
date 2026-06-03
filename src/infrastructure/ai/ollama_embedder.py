from __future__ import annotations

import httpx

from src.domain.ports.embedding_port import EmbeddingPort


class OllamaEmbedder(EmbeddingPort):
    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dim: int | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if self._dim is None and embeddings:
            self._dim = len(embeddings[0])
        return embeddings

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, query: str) -> list[float]:
        return self._embed([query])[0]

    def get_dimension(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed_query("dimension probe"))
        return self._dim

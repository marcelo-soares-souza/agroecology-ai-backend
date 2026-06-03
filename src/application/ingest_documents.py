from __future__ import annotations

import asyncio
import threading

from src.domain.ports.embedding_port import EmbeddingPort
from src.domain.ports.ingestion_repository import IngestionRepository
from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import CHUNK_OVERLAP, CHUNK_SIZE


class IngestDocuments:
    def __init__(
        self,
        vector_store: VectorStorePort,
        embedder: EmbeddingPort,
        ingestion_repo: IngestionRepository,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._ingestion_repo = ingestion_repo
        self._lock = threading.Lock()
        self.status: str = "idle"
        self.chunks_indexed: int = 0
        self.error: str | None = None
        self.current_run_id: str | None = None

    def start(self) -> bool:
        with self._lock:
            if self.status == "processing":
                return False
            self.status = "processing"
            self.chunks_indexed = 0
            self.error = None
            self.current_run_id = None

        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return True

    def _run(self) -> None:
        run_id: str | None = None
        try:
            run = asyncio.run(self._ingestion_repo.insert())
            run_id = run.id
            with self._lock:
                self.current_run_id = run_id

            count = self._ingest_all()

            asyncio.run(
                self._ingestion_repo.update(run_id, status="done", chunks_indexed=count)
            )
            with self._lock:
                self.status = "done"
                self.chunks_indexed = count
                self.error = None
        except Exception as e:
            error_msg = str(e)
            with self._lock:
                self.status = "error"
                self.chunks_indexed = 0
                self.error = error_msg
                if self.current_run_id:
                    run_id = self.current_run_id
            if run_id:
                try:
                    asyncio.run(
                        self._ingestion_repo.update(
                            run_id, status="error", error=error_msg
                        )
                    )
                except Exception:
                    pass

    def _ingest_all(self) -> int:
        from pathlib import Path

        from src.domain.services.chunker import chunk_text
        from src.shared.config import (
            DATA_DIR_MARKDOWN,
            DATA_DIR_PDFS,
            DATA_DIR_WEB,
        )

        docs = self._load_all(DATA_DIR_PDFS, DATA_DIR_MARKDOWN, DATA_DIR_WEB)
        if not docs:
            raise ValueError(
                "No documents found. "
                "Add files to data/pdfs/, data/markdown/ or data/web/"
            )

        rows: list[dict] = []
        for doc in docs:
            chunks = chunk_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                rows.append(
                    {
                        "id": f"{Path(doc['source']).stem}_{i}",
                        "text": chunk,
                        "source": doc["source"],
                        "chunk_index": i,
                    }
                )

        texts = [r["text"] for r in rows]
        vectors = self._embedder.embed_texts(texts)
        for i, row in enumerate(rows):
            row["vector"] = vectors[i]

        self._vector_store.build_index(rows, self._embedder.get_dimension())
        return len(rows)

    @staticmethod
    def _load_all(pdf_dir, md_dir, web_dir) -> list[dict]:

        import fitz
        from src.shared.config import DATA_DIR

        sources: list[dict] = []

        for fp in pdf_dir.glob("*.pdf"):
            try:
                pdf = fitz.open(str(fp))
                text = "\n".join(page.get_text() for page in pdf)
                pdf.close()
                if text.strip():
                    rel = str(fp.relative_to(DATA_DIR))
                    sources.append({"text": text, "source": rel})
            except Exception:
                pass

        for fp in md_dir.glob("*.md"):
            text = fp.read_text(encoding="utf-8")
            if text.strip():
                rel = str(fp.relative_to(DATA_DIR))
                sources.append({"text": text, "source": rel})

        for fp in web_dir.glob("*.txt"):
            text = fp.read_text(encoding="utf-8")
            if text.strip():
                rel = str(fp.relative_to(DATA_DIR))
                sources.append({"text": text, "source": rel})

        return sources

    def to_dict(self) -> dict:
        with self._lock:
            result: dict = {"status": self.status}
            if self.status == "done":
                result["chunks_indexed"] = self.chunks_indexed
            elif self.status == "error":
                result["error"] = self.error
            if self.current_run_id:
                result["run_id"] = self.current_run_id
            return result

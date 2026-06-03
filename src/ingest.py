from pathlib import Path

import lancedb

from .chunker import chunk_text
from .config import CHUNK_OVERLAP, CHUNK_SIZE, LANCEDB_DIR
from .embedder import embed_texts
from .loader import load_all_documents


def ingest_all() -> tuple[object, int]:
    docs = load_all_documents()
    if not docs:
        raise ValueError(
            "No documents found. Add files to data/pdfs/, data/markdown/ or data/web/"
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
    vectors = embed_texts(texts)

    for i, row in enumerate(rows):
        row["vector"] = vectors[i]

    db = lancedb.connect(str(LANCEDB_DIR))
    table = db.create_table("chunks", data=rows, mode="overwrite")

    return table, len(rows)


def check_index_exists() -> bool:
    if not LANCEDB_DIR.exists():
        return False
    db = lancedb.connect(str(LANCEDB_DIR))
    return "chunks" in db.table_names()

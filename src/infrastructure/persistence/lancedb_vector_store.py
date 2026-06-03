from __future__ import annotations

from typing import Any

from src.domain.ports.vector_store_port import VectorStorePort
from src.shared.config import LANCEDB_DIR


class LanceDBVectorStore(VectorStorePort):
    def __init__(self) -> None:
        import lancedb

        self._dir = LANCEDB_DIR
        self._db = lancedb.connect(str(LANCEDB_DIR))

    def _get_table(self):
        db = self._db
        if "chunks" not in db.table_names():
            raise FileNotFoundError(
                f"Table 'chunks' not found in {self._dir}. Run: python main.py ingest"
            )
        return db.open_table("chunks")

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        table = self._get_table()
        results = table.search(query_vector).metric("cosine").limit(top_k).to_list()
        for r in results:
            r["_search_type"] = "vector"
        return results

    def index_exists(self) -> bool:
        if not self._dir.exists():
            return False
        return "chunks" in self._db.table_names()

    def build_index(self, rows: list[dict[str, Any]], dimension: int) -> None:
        self._db.create_table("chunks", data=rows, mode="overwrite")

    def get_all_rows(self) -> list[dict[str, Any]]:
        table = self._get_table()
        return table.to_arrow().to_pylist()

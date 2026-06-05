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

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        table = self._get_table()
        query = table.search(query_vector).metric("cosine").limit(top_k)
        if filters:
            where_clause = self._build_where(filters)
            if where_clause:
                query = query.where(where_clause)
        results = query.to_list()
        for r in results:
            r["_search_type"] = "vector"
        return results

    @staticmethod
    def _build_where(filters: dict[str, Any]) -> str | None:
        conditions: list[str] = []
        for key, value in filters.items():
            if isinstance(value, int):
                conditions.append(f"{key} = {value}")
            elif isinstance(value, str):
                escaped = value.replace("'", "''")
                conditions.append(f"{key} = '{escaped}'")
            elif isinstance(value, tuple) and len(value) == 2:
                conditions.append(f"{key} >= {value[0]} AND {key} <= {value[1]}")
        return " AND ".join(conditions) if conditions else None

    def index_exists(self) -> bool:
        if not self._dir.exists():
            return False
        return "chunks" in self._db.table_names()

    def build_index(self, rows: list[dict[str, Any]], dimension: int) -> None:
        self._db.create_table("chunks", data=rows, mode="overwrite")

    def get_all_rows(self) -> list[dict[str, Any]]:
        table = self._get_table()
        return table.to_arrow().to_pylist()

    def add_rows(self, rows: list[dict[str, Any]]) -> None:
        table = self._get_table()
        table.add(rows)

    def delete_by_prefix(self, id_prefix: str) -> None:
        table = self._get_table()
        table.delete(f"id LIKE '{id_prefix}%'")

    def count_chunks(self) -> int:
        table = self._get_table()
        return table.count_rows()

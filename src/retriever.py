from rank_bm25 import BM25Okapi

from .config import BM25_TOP_K, HYBRID_TOP_K, LANCEDB_DIR, SIMILARITY_TOP_K
from .embedder import embed_query

import lancedb


def _get_table():
    db = lancedb.connect(str(LANCEDB_DIR))
    table_names = db.table_names()
    if "chunks" not in table_names:
        raise FileNotFoundError(
            f"Table 'chunks' not found in {LANCEDB_DIR}. Run: python main.py ingest"
        )
    return db.open_table("chunks")


def _build_bm25(texts: list[str]) -> BM25Okapi:
    tokenized = [text.lower().split() for text in texts]
    return BM25Okapi(tokenized)


def vector_search(query: str, top_k: int = SIMILARITY_TOP_K) -> list[dict]:
    table = _get_table()
    query_vec = embed_query(query)
    results = table.search(query_vec).metric("cosine").limit(top_k).to_list()
    for r in results:
        r["_search_type"] = "vector"
    return results


def bm25_search(query: str, top_k: int = BM25_TOP_K) -> list[dict]:
    table = _get_table()
    all_rows = table.to_arrow().to_pylist()
    texts = [str(r["text"]) for r in all_rows]
    bm25 = _build_bm25(texts)
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)
    top = indexed[:top_k]
    results = []
    for idx, score in top:
        row = dict(all_rows[idx])
        row["_distance"] = float(score)
        row["_search_type"] = "bm25"
        results.append(row)
    return results


def _rrf_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    scores: dict[str, float] = {}
    rows: dict[str, dict] = {}

    for rank, r in enumerate(vector_results):
        doc_id = r["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        rows[doc_id] = r

    for rank, r in enumerate(bm25_results):
        doc_id = r["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        rows[doc_id] = r

    sorted_ids = sorted(scores, key=lambda k: scores[k], reverse=True)
    results = []
    for doc_id in sorted_ids:
        row = dict(rows[doc_id])
        row["_rrf_score"] = scores[doc_id]
        results.append(row)
    return results


def hybrid_search(query: str, top_k: int = HYBRID_TOP_K) -> list[dict]:
    vec_results = vector_search(query, top_k=SIMILARITY_TOP_K)
    bm25_results = bm25_search(query, top_k=BM25_TOP_K)

    if not bm25_results:
        return vec_results[:top_k]

    fused = _rrf_fusion(vec_results, bm25_results)
    return fused[:top_k]

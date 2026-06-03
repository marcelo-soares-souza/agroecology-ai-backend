from openai import OpenAI

from .config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    SIMILARITY_TOP_K,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from .ingest import check_index_exists
from .retriever import hybrid_search

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not DEEPSEEK_API_KEY:
            raise ValueError(
                "DEEPSEEK_API_KEY not configured. "
                "Create a .env file with DEEPSEEK_API_KEY=sk-..."
            )
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def build_context(retrieved: list[dict]) -> str:
    parts = []
    for i, r in enumerate(retrieved, 1):
        source = r.get("source", "unknown")
        text = r["text"].strip()
        parts.append(f"[{i}] (source: {source})\n{text}")
    return "\n\n".join(parts)


def _retrieve_context(question: str, top_k: int) -> list[dict]:
    return hybrid_search(question, top_k=top_k)


def ask(question: str, top_k: int = SIMILARITY_TOP_K) -> str:
    result = ask_with_sources(question, top_k=top_k)
    return result["answer"]


def ask_with_sources(
    question: str,
    top_k: int = SIMILARITY_TOP_K,
) -> dict:
    if not check_index_exists():
        raise FileNotFoundError("Index not found. Run: python main.py ingest")

    retrieved = _retrieve_context(question, top_k=top_k)
    context = build_context(retrieved)

    client = _get_client()
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT.format(context=context, question=question),
            },
        ],
        temperature=0.2,
        max_tokens=2048,
    )

    answer = response.choices[0].message.content or ""

    sources = []
    for node in retrieved:
        dist = node.get("_distance", 0)
        score = 1.0 / (1.0 + float(dist)) if dist else 0.0
        sources.append(
            {
                "text": node["text"][:300],
                "score": round(score, 4),
                "metadata": {
                    "source": node.get("source", "unknown"),
                    "chunk_index": node.get("chunk_index", 0),
                    "search_type": node.get("_search_type", "unknown"),
                },
            }
        )

    return {"answer": answer, "sources": sources}

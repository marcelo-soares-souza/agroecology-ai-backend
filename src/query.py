import re

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
_CONTEXT_DEPENDENT_PATTERNS = (
    re.compile(r"^\s*(and|also|what about|how about)\b", re.IGNORECASE),
    re.compile(r"\b(this|that|it|they|them|those|these)\b", re.IGNORECASE),
    re.compile(
        r"\b(tell me more|more detail|more details|expand on|go deeper)\b",
        re.IGNORECASE,
    ),
)
_MAX_HISTORY_TURNS = 6
_MAX_HISTORY_SNIPPET_CHARS = 500


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
    history: list[dict] | None = None,
) -> dict:
    if not check_index_exists():
        raise FileNotFoundError("Index not found. Run: python main.py ingest")

    search_query = _build_search_query(question, history or [])
    retrieved = _retrieve_context(search_query, top_k=top_k)
    context = build_context(retrieved)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        recent = history[-(_MAX_HISTORY_TURNS * 2) :]
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": USER_PROMPT.format(context=context, question=question),
        }
    )

    client = _get_client()
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
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


def _build_search_query(question: str, history: list[dict]) -> str:
    if not history or not _is_context_dependent_question(question):
        return question

    last_user = _find_last_message(history, "user")
    last_assistant = _find_last_message(history, "assistant")
    if not last_user and not last_assistant:
        return question

    snippets = [f"Current follow-up question: {question.strip()}"]
    if last_user:
        snippets.append(f"Previous user question: {_normalize_snippet(last_user)}")
    if last_assistant:
        snippets.append(
            f"Previous assistant answer: {_normalize_snippet(last_assistant)}"
        )
    return "\n".join(snippets)


def _is_context_dependent_question(question: str) -> bool:
    compact_question = " ".join(question.strip().split())
    if not compact_question:
        return False
    if len(compact_question.split()) <= 4:
        return True
    return any(
        pattern.search(compact_question) for pattern in _CONTEXT_DEPENDENT_PATTERNS
    )


def _find_last_message(history: list[dict], role: str) -> str:
    for message in reversed(history):
        if message.get("role") == role and message.get("content"):
            return str(message["content"])
    return ""


def _normalize_snippet(content: str) -> str:
    compact_content = " ".join(content.split())
    return compact_content[:_MAX_HISTORY_SNIPPET_CHARS]

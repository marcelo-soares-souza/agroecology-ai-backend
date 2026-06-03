from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import redis
else:
    try:
        import redis  # noqa: F811
    except ImportError:
        redis = None  # type: ignore[assignment]


class ValkeyCache:
    def __init__(self, url: str, ttl: int = 3600) -> None:
        self.enabled = False
        self._client: redis.Redis | None = None  # type: ignore[name-defined]
        self._ttl = ttl

        if redis is None:
            logger.warning("redis package not installed, cache disabled")
            return

        try:
            self._client = redis.Redis.from_url(
                url, socket_connect_timeout=2, decode_responses=True
            )
            self._client.ping()
            self.enabled = True
            logger.info("Valkey cache connected: %s", url)
        except Exception:
            logger.warning("Valkey unavailable at %s, cache disabled", url)

    def _key(self, question: str) -> str:
        normalized = unicodedata.normalize("NFKD", question.lower().strip())
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        h = hashlib.md5(normalized.encode()).hexdigest()
        return f"rag:cache:{h}"

    def get(self, question: str) -> dict[str, Any] | None:
        if not self.enabled or self._client is None:
            return None
        try:
            raw: Any = self._client.get(self._key(question))
            if raw:
                self._client.incr("rag:stats:cache_hits")
                return dict(json.loads(str(raw)))
        except Exception:
            pass
        return None

    def set(self, question: str, result: dict[str, Any]) -> None:
        if not self.enabled or self._client is None:
            return
        try:
            self._client.setex(
                self._key(question),
                self._ttl,
                json.dumps(result, ensure_ascii=False),
            )
        except Exception:
            pass

    def hit_count(self) -> int:
        if not self.enabled or self._client is None:
            return 0
        try:
            raw: Any = self._client.get("rag:stats:cache_hits")
            return int(str(raw)) if raw else 0
        except Exception:
            return 0

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

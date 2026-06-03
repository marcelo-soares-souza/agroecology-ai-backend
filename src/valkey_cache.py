import hashlib
import json
import logging

logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:
    redis = None


class ValkeyCache:
    def __init__(self, url: str, ttl: int = 3600) -> None:
        self.enabled = False
        self._client: "redis.Redis | None" = None
        self._ttl = ttl

        if redis is None:
            logger.warning("redis package not installed, cache disabled")
            return

        try:
            self._client = redis.Redis.from_url(url, socket_connect_timeout=2, decode_responses=True)
            self._client.ping()
            self.enabled = True
            logger.info("Valkey cache connected: %s", url)
        except Exception:
            logger.warning("Valkey unavailable at %s, cache disabled", url)

    def _key(self, question: str) -> str:
        normalized = question.lower().strip()
        h = hashlib.md5(normalized.encode()).hexdigest()
        return f"rag:cache:{h}"

    def get(self, question: str) -> dict | None:
        if not self.enabled or self._client is None:
            return None
        try:
            raw = self._client.get(self._key(question))
            if raw:
                self._client.incr("rag:stats:cache_hits")
                return json.loads(raw)
        except Exception:
            pass
        return None

    def set(self, question: str, result: dict) -> None:
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
            raw = self._client.get("rag:stats:cache_hits")
            return int(raw) if raw else 0
        except Exception:
            return 0

    def close(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

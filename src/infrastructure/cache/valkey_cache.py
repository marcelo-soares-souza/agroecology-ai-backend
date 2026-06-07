from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from typing import TYPE_CHECKING, Any

from src.domain.dto.answer_result import AnswerResult
from src.domain.ports.cache_port import CachePort
from src.shared.logging_utils import log_event

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import redis
else:
    try:
        import redis  # noqa: F811
    except ImportError:
        redis = None  # type: ignore[assignment]

_KEY_PREFIX = "rag:cache:v"


class ValkeyCache(CachePort):  # noqa: F811
    def __init__(self, url: str, ttl: int = 3600) -> None:
        self.enabled = False
        self._client: redis.Redis | None = None  # type: ignore[name-defined]
        self._ttl = ttl
        self._index_version = "0"
        self._embedding_model = ""
        self._reranker_model = ""
        self._top_k = 0

        if redis is None:
            log_event(logger, logging.WARNING, "cache_disabled", reason="redis_missing")
            return

        try:
            self._client = redis.Redis.from_url(
                url, socket_connect_timeout=2, decode_responses=True
            )
            self._client.ping()
            self.enabled = True
            log_event(
                logger, logging.INFO, "cache_connected", backend="valkey", url=url
            )
        except Exception:
            log_event(
                logger,
                logging.WARNING,
                "cache_disabled",
                reason="connection_failed",
                url=url,
            )

    def set_index_version(self, version: str) -> None:
        self._index_version = version
        log_event(logger, logging.INFO, "cache_index_version_updated", version=version)

    def invalidate_all(self) -> None:
        if not self.enabled or self._client is None:
            return
        try:
            pattern = f"{_KEY_PREFIX}:{self._index_version}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = self._client.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    deleted += self._client.delete(*keys)
                if cursor == 0:
                    break
            log_event(
                logger,
                logging.INFO,
                "cache_invalidated",
                version=self._index_version,
                keys_deleted=deleted,
            )
        except Exception:
            pass

    def configure(
        self,
        embedding_model: str,
        reranker_model: str,
        top_k: int,
    ) -> None:
        self._embedding_model = embedding_model
        self._reranker_model = reranker_model
        self._top_k = top_k

    def _key(self, question: str, top_k: int = 0) -> str:
        normalized = unicodedata.normalize("NFKD", question.lower().strip())
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        effective_top_k = top_k if top_k > 0 else self._top_k
        payload = f"{normalized}|v{self._index_version}|emb={self._embedding_model}|rerank={self._reranker_model}|k={effective_top_k}"
        h = hashlib.md5(payload.encode()).hexdigest()
        return f"{_KEY_PREFIX}:{self._index_version}:{h}"

    def get(self, question: str, top_k: int = 0) -> AnswerResult | None:
        if not self.enabled or self._client is None:
            return None
        try:
            raw: Any = self._client.get(self._key(question, top_k))
            if raw:
                self._client.incr("rag:stats:cache_hits")
                log_event(logger, logging.INFO, "cache_hit")
                return AnswerResult.from_cache_dict(json.loads(str(raw)))
        except Exception:
            pass
        log_event(logger, logging.INFO, "cache_miss")
        return None

    def set(self, question: str, result: AnswerResult, top_k: int = 0) -> None:
        if not self.enabled or self._client is None:
            return
        try:
            self._client.setex(
                self._key(question, top_k),
                self._ttl,
                json.dumps(result.to_cache_dict(), ensure_ascii=False),
            )
            log_event(logger, logging.INFO, "cache_set", ttl=self._ttl)
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
                log_event(logger, logging.INFO, "cache_closed")
            except Exception:
                pass

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from src.domain.dto.auth_rate_limit import AuthRateLimitBlock
from src.domain.ports.auth_rate_limiter_port import AuthRateLimiterPort
from src.shared.logging_utils import log_event

logger = logging.getLogger("agroecology.auth_rate_limit")

if TYPE_CHECKING:
    import redis
else:
    try:
        import redis  # noqa: F401
    except ImportError:
        redis = None  # type: ignore[assignment]

_KEY_PREFIX = "auth:rate-limit"


class ValkeyAuthRateLimiter(AuthRateLimiterPort):  # noqa: F811
    """Valkey-backed rate limiter for public authentication endpoints."""

    def __init__(self, url: str, max_failures: int, block_seconds: int) -> None:
        self.enabled = False
        self._client: redis.Redis | None = None  # type: ignore[name-defined]
        self._max_failures = max(1, max_failures)
        self._block_seconds = max(1, block_seconds)

        if redis is None:
            log_event(
                logger,
                logging.WARNING,
                "auth_rate_limiter_disabled",
                reason="redis_missing",
            )
            return

        try:
            self._client = redis.Redis.from_url(
                url, socket_connect_timeout=2, decode_responses=True
            )
            self._client.ping()
            self.enabled = True
            log_event(
                logger,
                logging.INFO,
                "auth_rate_limiter_connected",
                backend="valkey",
                url=url,
            )
        except Exception:
            log_event(
                logger,
                logging.WARNING,
                "auth_rate_limiter_disabled",
                reason="connection_failed",
                url=url,
            )

    def get_block(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        if not self.enabled or self._client is None:
            return None

        blocks = [
            block
            for key in self._keys(action, identifiers, "blocked")
            if (block := self._block_for_key(key)) is not None
        ]
        return _latest_block(blocks)

    def record_failure(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        if not self.enabled or self._client is None:
            return None

        existing = self.get_block(action, identifiers)
        if existing is not None:
            return existing

        blocks: list[AuthRateLimitBlock] = []
        for key in self._keys(action, identifiers, "failures"):
            try:
                count = int(self._client.incr(key))
                if count == 1:
                    self._client.expire(key, self._block_seconds)
                if count >= self._max_failures:
                    block_key = key.replace(":failures:", ":blocked:", 1)
                    self._client.setex(block_key, self._block_seconds, "1")
                    self._client.delete(key)
                    block = self._block_for_key(block_key)
                    if block is not None:
                        blocks.append(block)
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "auth_rate_limit_record_failed",
                    error=str(exc),
                )

        return _latest_block(blocks)

    def reset(self, action: str, identifiers: Sequence[str]) -> None:
        if not self.enabled or self._client is None:
            return
        try:
            keys = self._keys(action, identifiers, "failures")
            if keys:
                self._client.delete(*keys)
        except Exception:
            pass

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

    def _block_for_key(self, key: str) -> AuthRateLimitBlock | None:
        assert self._client is not None
        try:
            ttl: Any = self._client.ttl(key)
        except Exception:
            return None

        retry_after = int(ttl)
        if retry_after <= 0:
            return None

        blocked_until = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
        return AuthRateLimitBlock(
            retry_after_seconds=retry_after,
            blocked_until=blocked_until,
        )

    def _keys(
        self,
        action: str,
        identifiers: Sequence[str],
        bucket: str,
    ) -> list[str]:
        return [
            f"{_KEY_PREFIX}:{bucket}:{_digest(action, identifier)}"
            for identifier in identifiers
            if identifier
        ]


def _digest(action: str, identifier: str) -> str:
    return hashlib.sha256(f"{action}:{identifier}".encode("utf-8")).hexdigest()


def _latest_block(
    blocks: Sequence[AuthRateLimitBlock],
) -> AuthRateLimitBlock | None:
    if not blocks:
        return None
    return max(blocks, key=lambda block: block.retry_after_seconds)

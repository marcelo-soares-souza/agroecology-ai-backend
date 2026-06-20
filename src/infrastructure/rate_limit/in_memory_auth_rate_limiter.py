from __future__ import annotations

import hashlib
import threading
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from src.domain.dto.auth_rate_limit import AuthRateLimitBlock
from src.domain.ports.auth_rate_limiter_port import AuthRateLimiterPort


class InMemoryAuthRateLimiter(AuthRateLimiterPort):
    """Process-local fallback for public auth rate limiting."""

    def __init__(self, max_failures: int, block_seconds: int) -> None:
        self._max_failures = max(1, max_failures)
        self._block_seconds = max(1, block_seconds)
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[int, datetime]] = {}
        self._blocks: dict[str, datetime] = {}

    def get_block(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup(now)
            blocks = [
                self._to_block(blocked_until, now)
                for key in self._keys(action, identifiers)
                if (blocked_until := self._blocks.get(key)) is not None
            ]
        return self._latest_block(blocks)

    def record_failure(
        self, action: str, identifiers: Sequence[str]
    ) -> AuthRateLimitBlock | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup(now)
            keys = self._keys(action, identifiers)
            existing_blocks = [
                self._to_block(blocked_until, now)
                for key in keys
                if (blocked_until := self._blocks.get(key)) is not None
            ]
            if existing_blocks:
                return self._latest_block(existing_blocks)

            new_blocks: list[AuthRateLimitBlock] = []
            for key in keys:
                count, expires_at = self._failures.get(
                    key, (0, now + timedelta(seconds=self._block_seconds))
                )
                if expires_at <= now:
                    count = 0
                    expires_at = now + timedelta(seconds=self._block_seconds)

                count += 1
                self._failures[key] = (count, expires_at)
                if count >= self._max_failures:
                    blocked_until = now + timedelta(seconds=self._block_seconds)
                    self._blocks[key] = blocked_until
                    self._failures.pop(key, None)
                    new_blocks.append(self._to_block(blocked_until, now))

        return self._latest_block(new_blocks)

    def reset(self, action: str, identifiers: Sequence[str]) -> None:
        with self._lock:
            for key in self._keys(action, identifiers):
                self._failures.pop(key, None)

    def _cleanup(self, now: datetime) -> None:
        expired_failures = [
            key for key, (_, expires_at) in self._failures.items() if expires_at <= now
        ]
        for key in expired_failures:
            self._failures.pop(key, None)

        expired_blocks = [
            key for key, blocked_until in self._blocks.items() if blocked_until <= now
        ]
        for key in expired_blocks:
            self._blocks.pop(key, None)

    def _keys(self, action: str, identifiers: Sequence[str]) -> list[str]:
        return [_key(action, identifier) for identifier in identifiers if identifier]

    @staticmethod
    def _to_block(blocked_until: datetime, now: datetime) -> AuthRateLimitBlock:
        retry_after = max(1, int((blocked_until - now).total_seconds()))
        return AuthRateLimitBlock(
            retry_after_seconds=retry_after,
            blocked_until=blocked_until,
        )

    @staticmethod
    def _latest_block(
        blocks: Sequence[AuthRateLimitBlock],
    ) -> AuthRateLimitBlock | None:
        if not blocks:
            return None
        return max(blocks, key=lambda block: block.retry_after_seconds)


def _key(action: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{action}:{digest}"

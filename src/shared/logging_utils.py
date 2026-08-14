"""Structured logging utilities with performance snapshots and IP resolution."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, cast

_default_formatter_class: type[logging.Formatter] | None

try:
    from uvicorn.logging import DefaultFormatter as _default_formatter_class
except Exception:  # pragma: no cover
    _default_formatter_class = None

_LOG_FORMAT = "%(levelprefix)s %(asctime)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


@dataclass(frozen=True)
class PerfSnapshot:
    """A point-in-time performance measurement.

    Attributes:
        wall_time: Monotonic wall-clock time in seconds.
        process_cpu_time: Process CPU time in seconds.
        thread_cpu_time: Thread CPU time in seconds.
        rss_mb: Resident Set Size in megabytes, or None if unavailable.
    """

    wall_time: float
    process_cpu_time: float
    thread_cpu_time: float
    rss_mb: float | None


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with a consistent format.

    Args:
        level: The logging level to set (default INFO).
    """
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    formatter: logging.Formatter
    if _default_formatter_class is not None:
        formatter_class = cast(type[logging.Formatter], _default_formatter_class)
        formatter = formatter_class(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
    else:
        formatter = logging.Formatter(
            _LOG_FORMAT.replace("%(levelprefix)s", "%(levelname)s"),
            datefmt=_DATE_FORMAT,
        )
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format=_LOG_FORMAT.replace("%(levelprefix)s", "%(levelname)s"),
            datefmt=_DATE_FORMAT,
        )
        return

    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def header_value(headers: Mapping[str, str], name: str) -> str:
    """Extract a stripped header value from a request headers mapping.

    Args:
        headers: The headers mapping.
        name: The header name to look up.

    Returns:
        The header value stripped of whitespace, or an empty string if absent.
    """
    return headers.get(name, "").strip()


def _trusted_proxy_hosts() -> set[str]:
    return {
        host.strip().lower()
        for host in os.getenv("TRUSTED_PROXY_HOSTS", "127.0.0.1,::1,localhost").split(
            ","
        )
        if host.strip()
    }


def _is_trusted_proxy(client_host: str | None) -> bool:
    if not client_host:
        return False
    hosts = _trusted_proxy_hosts()
    normalized = client_host.strip().lower().strip("[]")
    return "*" in hosts or normalized in hosts


def resolve_client_ip(headers: Mapping[str, str], client_host: str | None) -> str:
    """Determine the originating client IP from request headers.

    Checks Cloudflare, X-Forwarded-For, and X-Real-IP headers in order,
    falling back to the client host or 'unknown'.

    Args:
        headers: The request headers mapping.
        client_host: The direct client host from the transport.

    Returns:
        The resolved client IP address string.
    """
    if _is_trusted_proxy(client_host):
        cf_connecting_ip = header_value(headers, "cf-connecting-ip")
        if cf_connecting_ip:
            return cf_connecting_ip

        forwarded_for = header_value(headers, "x-forwarded-for")
        if forwarded_for:
            first_hop = forwarded_for.split(",")[0].strip()
            if first_hop:
                return first_hop

        real_ip = header_value(headers, "x-real-ip")
        if real_ip:
            return real_ip

    return client_host or "unknown"


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit a structured log message with key=value fields.

    Args:
        logger: The logger instance to use.
        level: The log level.
        event: The event name (logged as event=...).
        **fields: Additional key-value pairs to include in the message.
    """
    parts = [f"event={event}"]
    for key in sorted(fields):
        value = fields[key]
        if value is None:
            continue
        text = str(value).replace("\n", "\\n")
        parts.append(f"{key}={text}")
    logger.log(level, " ".join(parts))


def take_perf_snapshot() -> PerfSnapshot:
    """Capture a point-in-time performance measurement.

    Returns:
        A PerfSnapshot with current wall, CPU, and memory metrics.
    """
    return PerfSnapshot(
        wall_time=time.perf_counter(),
        process_cpu_time=time.process_time(),
        thread_cpu_time=time.thread_time(),
        rss_mb=_read_rss_mb(),
    )


def perf_fields(
    started_at: PerfSnapshot,
    prefix: str = "",
) -> dict[str, float | None]:
    """Compute elapsed performance metrics since a starting snapshot.

    Args:
        started_at: The snapshot taken at the start of the operation.
        prefix: An optional prefix for the metric key names.

    Returns:
        A dict of metric names to elapsed values (ms for time, MB for RSS).
    """
    now = take_perf_snapshot()
    key_prefix = f"{prefix}_" if prefix else ""
    rss_delta_mb = None
    if started_at.rss_mb is not None and now.rss_mb is not None:
        rss_delta_mb = round(now.rss_mb - started_at.rss_mb, 2)
    return {
        f"{key_prefix}wall_ms": round((now.wall_time - started_at.wall_time) * 1000, 2),
        f"{key_prefix}cpu_process_ms": round(
            (now.process_cpu_time - started_at.process_cpu_time) * 1000, 2
        ),
        f"{key_prefix}cpu_thread_ms": round(
            (now.thread_cpu_time - started_at.thread_cpu_time) * 1000, 2
        ),
        f"{key_prefix}rss_mb": round(now.rss_mb, 2) if now.rss_mb is not None else None,
        f"{key_prefix}rss_delta_mb": rss_delta_mb,
    }


def _read_rss_mb() -> float | None:
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as statm:
            parts = statm.read().split()
        if len(parts) < 2:
            return None
        rss_pages = int(parts[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
        return rss_pages * page_size / (1024 * 1024)
    except (FileNotFoundError, OSError, ValueError):
        return None


def mask_email(email: str | None) -> str:
    """Mask an email address for safe logging.

    Args:
        email: The email address to mask.

    Returns:
        The masked email (e.g., 'j***e@example.com'), or 'unknown' if invalid.
    """
    if not email or "@" not in email:
        return "unknown"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def truncate_for_log(value: Any, limit: int = 3000) -> str:
    """Truncate a value's string representation for safe logging.

    Args:
        value: The value to convert to string.
        limit: Maximum character length.

    Returns:
        The truncated string with a truncation notice if shortened.
    """
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...<truncated {len(text) - limit} chars>"


def preview_for_log(value: Any, limit: int = 160) -> str:
    """Return a compact single-line preview for structured logs."""
    if value is None:
        return "-"
    text = " ".join(str(value).split())
    if not text:
        return "-"
    if len(text) <= limit:
        return text
    return f"{text[: max(limit - 3, 0)].rstrip()}..."


def hash_for_log(value: Any, length: int = 12) -> str:
    """Return a short stable hash for correlating sensitive or long values."""
    if value is None:
        return "-"
    text = str(value).strip()
    if not text:
        return "-"
    return sha256(text.encode("utf-8")).hexdigest()[:length]


def round_float_for_log(value: float | None, digits: int = 3) -> float | None:
    """Round a float for readable structured logs."""
    if value is None:
        return None
    return round(value, digits)

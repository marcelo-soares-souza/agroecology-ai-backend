from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

_default_formatter_class: type[logging.Formatter] | None

try:
    from uvicorn.logging import DefaultFormatter as _default_formatter_class
except Exception:  # pragma: no cover
    _default_formatter_class = None

_LOG_FORMAT = "%(levelprefix)s %(asctime)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: int = logging.INFO) -> None:
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
    return headers.get(name, "").strip()


def resolve_client_ip(headers: Mapping[str, str], client_host: str | None) -> str:
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
    parts = [f"event={event}"]
    for key in sorted(fields):
        value = fields[key]
        if value is None:
            continue
        text = str(value).replace("\n", "\\n")
        parts.append(f"{key}={text}")
    logger.log(level, " ".join(parts))


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "unknown"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = "*" * len(local)
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"

from __future__ import annotations

import logging
from typing import Any


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

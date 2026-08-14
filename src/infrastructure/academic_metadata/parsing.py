from __future__ import annotations

import re
from typing import Any


def collapse_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def strip_markup(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    return collapse_whitespace(value)


def clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    return value or None


def parse_year(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.match(r"^\d{4}", value):
        return int(value[:4])
    return None


def first_string(values: Any) -> str | None:
    if isinstance(values, str):
        return collapse_whitespace(values)
    if isinstance(values, list) and values:
        first = values[0]
        if isinstance(first, str):
            return collapse_whitespace(first)
    return None

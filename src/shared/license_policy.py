from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


BLOCK_FULL_PDF_LICENSE_URL_PATTERNS = (
    re.compile(r"elsevier\.com", re.IGNORECASE),
    re.compile(r"springer", re.IGNORECASE),
    re.compile(r"wiley", re.IGNORECASE),
    re.compile(r"cambridge\.org", re.IGNORECASE),
    re.compile(r"sagepub\.com", re.IGNORECASE),
)


def is_full_file_access_blocked(file_type: str, license_value: Any) -> bool:
    if file_type != "pdf" or license_value is None:
        return False

    return any(
        pattern.search(url)
        for url in _iter_license_urls(license_value)
        for pattern in BLOCK_FULL_PDF_LICENSE_URL_PATTERNS
    )


def _iter_license_urls(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if key.lower() == "url" and isinstance(nested_value, str):
                yield nested_value
            elif isinstance(nested_value, (Mapping, list)):
                yield from _iter_license_urls(nested_value)
        return

    if isinstance(value, list):
        for item in value:
            yield from _iter_license_urls(item)

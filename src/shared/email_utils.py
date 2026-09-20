from __future__ import annotations

import re

MAX_EMAIL_LENGTH = 254
MAX_LOCAL_PART_LENGTH = 64
MAX_DOMAIN_LENGTH = 255
MAX_DOMAIN_LABEL_LENGTH = 63

_LOCAL_PART_PATTERN = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$")
_DOMAIN_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$")


def normalize_email(email: str) -> str:
    """Return a canonical email representation for storage and lookup."""
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    """Check whether an email address is syntactically valid.

    Pragmatic RFC 5321/5322 validation: single @, valid local part,
    dot-separated domain labels, and a plausible alphabetic TLD.
    """
    if not email or len(email) > MAX_EMAIL_LENGTH:
        return False

    if email.count("@") != 1:
        return False

    local_part, domain = email.rsplit("@", 1)

    if not local_part or len(local_part) > MAX_LOCAL_PART_LENGTH:
        return False
    if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
        return False
    if not _LOCAL_PART_PATTERN.match(local_part):
        return False

    if not domain or len(domain) > MAX_DOMAIN_LENGTH:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in domain:
        return False

    labels = domain.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if (
            not label
            or len(label) > MAX_DOMAIN_LABEL_LENGTH
            or not _DOMAIN_LABEL_PATTERN.match(label)
        ):
            return False

    tld = labels[-1]
    return tld.isalpha() and len(tld) >= 2


def validate_email(email: str) -> str:
    """Normalize and validate an email address.

    Raises:
        ValueError: If the address is not syntactically valid.

    Returns:
        The normalized email address.
    """
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        raise ValueError("Invalid email address")
    return normalized

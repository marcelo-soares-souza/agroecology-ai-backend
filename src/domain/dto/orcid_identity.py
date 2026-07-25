from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrcidIdentity:
    orcid_id: str
    name: str | None
    email: str | None
    slug: str | None = None

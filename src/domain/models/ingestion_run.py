from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IngestionRun:
    id: str
    status: str
    chunks_indexed: int
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None

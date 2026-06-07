from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceResult:
    text: str
    score: float
    score_type: str
    rank: int
    metadata: dict = field(default_factory=dict)


@dataclass
class AnswerResult:
    answer: str
    sources: list[SourceResult] = field(default_factory=list)

    def to_cache_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": [
                {
                    "text": s.text,
                    "score": s.score,
                    "score_type": s.score_type,
                    "rank": s.rank,
                    "metadata": s.metadata,
                }
                for s in self.sources
            ],
        }

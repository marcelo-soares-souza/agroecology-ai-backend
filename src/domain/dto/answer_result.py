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

    @classmethod
    def from_cache_dict(cls, data: dict) -> AnswerResult:
        sources = [
            SourceResult(
                text=str(item.get("text", "")),
                score=float(item.get("score", 0.0) or 0.0),
                score_type=str(item.get("score_type", "unknown")),
                rank=int(item.get("rank", 0) or 0),
                metadata=dict(item.get("metadata", {}) or {}),
            )
            for item in data.get("sources", [])
        ]
        return cls(
            answer=str(data.get("answer", "")),
            sources=sources,
        )

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

    def to_source_dicts(self) -> list[dict]:
        return [
            {
                "text": s.text,
                "score": s.score,
                "score_type": s.score_type,
                "rank": s.rank,
                "metadata": s.metadata,
            }
            for s in self.sources
        ]


@dataclass(frozen=True)
class TaskSubmissionResult:
    task_id: str
    status: str

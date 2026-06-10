from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceResult:
    """A single source citation from a retrieval result.

    Attributes:
        text: The source text excerpt.
        score: The relevance score.
        score_type: The type of score (e.g., 'distance', 'rerank').
        rank: The source's rank position.
        metadata: Additional metadata about the source.
    """

    text: str
    score: float
    score_type: str
    rank: int
    metadata: dict = field(default_factory=dict)


@dataclass
class AnswerResult:
    """The final Q&A response with cited sources.

    Attributes:
        answer: The generated answer text.
        sources: The list of source citations used in the answer.
    """

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
    """Result of submitting an async task.

    Attributes:
        task_id: The assigned task identifier.
        status: The initial task status.
    """

    task_id: str
    status: str

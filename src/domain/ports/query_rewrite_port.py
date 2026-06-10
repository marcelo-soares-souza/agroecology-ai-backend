from __future__ import annotations

from abc import ABC, abstractmethod


class QueryRewritePort(ABC):
    """Port for rewriting context-dependent questions into standalone queries.

    Resolves pronouns and implicit references from conversation history
    so the retrieval step receives a self-contained search query.
    """

    @abstractmethod
    def rewrite(self, question: str, history: list[dict]) -> str:
        """Rewrite a context-dependent question into a standalone query.

        Args:
            question: The user's current question.
            history: The conversation history as a list of role/content dicts.

        Returns:
            The rewritten standalone query, or the original question if no
            rewrite is needed.
        """

from abc import ABC, abstractmethod


class QueryRewritePort(ABC):
    @abstractmethod
    def rewrite(self, question: str, history: list[dict]) -> str:
        """Rewrite a context-dependent question into a standalone query.

        Returns the original question if no rewrite is needed.
        """

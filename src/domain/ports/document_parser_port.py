from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.parsed_document import ParsedDocument


class DocumentParserPort(ABC):
    """Port for parsing raw document bytes into structured blocks.

    Converts binary document content into a ParsedDocument containing
    typed, ordered blocks suitable for chunking.
    """

    @abstractmethod
    def parse(self, content: bytes, document_id: str, source: str) -> ParsedDocument:
        """Parse document content into a ParsedDocument with structured blocks.

        Args:
            content: The raw file bytes.
            document_id: The document's unique identifier.
            source: The source path or identifier of the document.

        Returns:
            The parsed document with structured blocks.
        """

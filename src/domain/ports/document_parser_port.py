from abc import ABC, abstractmethod

from src.domain.models.parsed_document import ParsedDocument


class DocumentParserPort(ABC):
    @abstractmethod
    def parse(self, content: bytes, document_id: str, source: str) -> ParsedDocument:
        """Parse document content into a ParsedDocument with structured blocks."""

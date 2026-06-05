from abc import ABC, abstractmethod
from pathlib import Path

from src.domain.models.parsed_document import ParsedDocument


class DocumentParserPort(ABC):
    @abstractmethod
    def parse(self, filepath: Path, document_id: str, source: str) -> ParsedDocument:
        """Parse a document file into a ParsedDocument with structured blocks."""

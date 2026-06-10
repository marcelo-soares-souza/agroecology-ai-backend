from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.models.parsed_document import ParsedDocument


@dataclass
class DocumentSource:
    """A document ready for ingestion, including its parsed content.

    Attributes:
        source_path: The path or identifier of the source file.
        doc_id: The unique document identifier.
        file_type: The file type (e.g., 'pdf', 'md').
        parsed: The parsed document with structured blocks.
    """

    source_path: str
    doc_id: str
    file_type: str
    parsed: ParsedDocument


class DocumentLoaderPort(ABC):
    """Port for loading all documents to be ingested.

    Iterates over available document sources and yields each one
    with its parsed content for processing.
    """

    @abstractmethod
    async def load_all(self) -> list[DocumentSource]:
        """Load all available document sources.

        Returns:
            A list of DocumentSource objects ready for ingestion.
        """

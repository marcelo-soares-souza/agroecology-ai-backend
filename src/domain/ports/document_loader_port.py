from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.models.document import Document
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
    """Port for loading registered documents to be ingested.

    The database is the source of truth for ingestion. Implementations must
    only load files for the document records they receive.
    """

    @abstractmethod
    async def load(self, documents: Sequence[Document]) -> list[DocumentSource]:
        """Load registered document sources.

        Args:
            documents: Document records selected for ingestion.

        Returns:
            A list of DocumentSource objects ready for ingestion.
        """

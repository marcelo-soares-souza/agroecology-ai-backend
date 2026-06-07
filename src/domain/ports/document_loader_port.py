from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.models.parsed_document import ParsedDocument


@dataclass
class DocumentSource:
    source_path: str
    doc_id: str
    file_type: str
    parsed: ParsedDocument


class DocumentLoaderPort(ABC):
    @abstractmethod
    async def load_all(self) -> list[DocumentSource]: ...

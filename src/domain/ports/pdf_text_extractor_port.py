from abc import ABC, abstractmethod


class PdfTextExtractorPort(ABC):
    @abstractmethod
    def extract_first_pages_text(self, content: bytes, max_pages: int = 3) -> str | None:
        pass

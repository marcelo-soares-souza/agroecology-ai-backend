from __future__ import annotations

from abc import ABC, abstractmethod


class PdfTextExtractorPort(ABC):
    """Port for extracting text from the first pages of a PDF.

    Used to obtain a preview of PDF content for metadata extraction
    or quality checks without processing the entire document.
    """

    @abstractmethod
    def extract_first_pages_text(
        self, content: bytes, max_pages: int = 3
    ) -> str | None:
        """Extract text from the first pages of a PDF.

        Args:
            content: The raw PDF file bytes.
            max_pages: Maximum number of pages to extract.

        Returns:
            The extracted text, or None if extraction fails.
        """

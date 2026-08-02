from __future__ import annotations

from abc import ABC, abstractmethod


class PdfTextExtractorPort(ABC):
    """Port for extracting text from the first pages of a PDF.

    Used to obtain a preview of PDF content for metadata extraction
    or quality checks without processing the entire document.
    """

    @abstractmethod
    def extract_first_pages_text(
        self, content: bytes, max_pages: int = 5
    ) -> str | None:
        """Extract text from the first pages of a PDF.

        Args:
            content: The raw PDF file bytes.
            max_pages: Maximum number of pages to extract.

        Returns:
            The extracted text, or None if extraction fails.
        """

    @abstractmethod
    def extract_pdf_metadata(self, content: bytes) -> dict[str, str]:
        """Extract embedded PDF file metadata.

        Args:
            content: The raw PDF file bytes.

        Returns:
            A mapping of metadata keys (e.g. "author", "title") to values,
            or an empty dict when the PDF cannot be read or has no metadata.
        """

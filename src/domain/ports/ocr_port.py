from __future__ import annotations

from abc import ABC, abstractmethod


class OcrPort(ABC):
    """Port for recognizing text in image-only document pages.

    Implementations receive encoded page images (e.g., PNG bytes) and
    return the recognized text for each image, preserving order.
    """

    @abstractmethod
    def ocr_images(self, images: list[bytes]) -> list[str]:
        """Recognize text in a batch of page images.

        Args:
            images: Encoded page images (PNG/JPEG bytes), one per page.

        Returns:
            The recognized text per image (empty string for failures),
            aligned by index with the input list.
        """

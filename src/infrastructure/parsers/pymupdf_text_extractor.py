from __future__ import annotations

from src.domain.ports.ocr_port import OcrPort
from src.domain.ports.pdf_text_extractor_port import PdfTextExtractorPort
from src.shared.config import OCR_DPI


class PyMuPdfTextExtractor(PdfTextExtractorPort):
    def __init__(self, ocr: OcrPort | None = None) -> None:
        self._ocr = ocr

    def extract_first_pages_text(
        self, content: bytes, max_pages: int = 5
    ) -> str | None:
        import fitz

        pdf_doc = None
        try:
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            pages = min(max_pages, len(pdf_doc))
            page_texts: list[tuple[int, str]] = []
            for i in range(pages):
                text = pdf_doc[i].get_text()
                if text:
                    page_texts.append((i, text))

            if len(page_texts) < pages and self._ocr is not None:
                missing = [
                    i for i in range(pages) if i not in {p for p, _ in page_texts}
                ]
                images = [
                    pdf_doc[i].get_pixmap(dpi=OCR_DPI).tobytes("png") for i in missing
                ]
                ocr_texts = self._ocr.ocr_images(images)
                page_texts.extend(
                    (i, text) for i, text in zip(missing, ocr_texts) if text
                )
                page_texts.sort(key=lambda item: item[0])

            texts = [text for _, text in page_texts if text]
            return "\n".join(texts) if texts else None
        except Exception:
            return None
        finally:
            if pdf_doc is not None:
                pdf_doc.close()

    def extract_pdf_metadata(self, content: bytes) -> dict[str, str]:
        import fitz

        pdf_doc = None
        try:
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            return {k: str(v or "") for k, v in dict(pdf_doc.metadata).items()}
        except Exception:
            return {}
        finally:
            if pdf_doc is not None:
                pdf_doc.close()

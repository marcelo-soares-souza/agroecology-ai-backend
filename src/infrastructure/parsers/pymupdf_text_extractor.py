from __future__ import annotations

from src.domain.ports.pdf_text_extractor_port import PdfTextExtractorPort


class PyMuPdfTextExtractor(PdfTextExtractorPort):
    def extract_first_pages_text(
        self, content: bytes, max_pages: int = 5
    ) -> str | None:
        import fitz

        pdf_doc = None
        try:
            pdf_doc = fitz.open(stream=content, filetype="pdf")
            pages = min(max_pages, len(pdf_doc))
            texts = []
            for i in range(pages):
                text = pdf_doc[i].get_text()
                if text:
                    texts.append(text)
            return "\n".join(texts) if texts else None
        except Exception:
            return None
        finally:
            if pdf_doc is not None:
                pdf_doc.close()

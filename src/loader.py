from pathlib import Path

import fitz

from .config import DATA_DIR, DATA_DIR_MARKDOWN, DATA_DIR_PDFS, DATA_DIR_WEB


def load_pdf(filepath: Path) -> str:
    doc = fitz.open(str(filepath))
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n".join(parts).strip()


def load_markdown(filepath: Path) -> str:
    return filepath.read_text(encoding="utf-8").strip()


def load_text(filepath: Path) -> str:
    return filepath.read_text(encoding="utf-8").strip()


def _relative_source(filepath: Path) -> str:
    try:
        return str(filepath.resolve().relative_to(DATA_DIR.resolve()))
    except ValueError:
        return filepath.name


def load_all_documents() -> list[dict]:
    documents: list[dict] = []

    for fp in sorted(DATA_DIR_PDFS.glob("*.pdf")):
        try:
            text = load_pdf(fp)
            if text:
                documents.append({"text": text, "source": _relative_source(fp)})
        except Exception as e:
            print(f"  [red]Error reading {fp.name}: {e}[/red]")

    for fp in sorted(DATA_DIR_MARKDOWN.glob("*.md")):
        try:
            text = load_markdown(fp)
            if text:
                documents.append({"text": text, "source": _relative_source(fp)})
        except Exception as e:
            print(f"  [red]Error reading {fp.name}: {e}[/red]")

    for fp in sorted(DATA_DIR_WEB.glob("*.txt")):
        try:
            text = load_text(fp)
            if text:
                documents.append({"text": text, "source": _relative_source(fp)})
        except Exception as e:
            print(f"  [red]Error reading {fp.name}: {e}[/red]")

    return documents

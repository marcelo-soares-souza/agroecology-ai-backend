import hashlib
from pathlib import Path
from urllib.parse import urlparse

import trafilatura

from .shared.config import DATA_DIR_WEB


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path
    slug = slug.rstrip("/").replace("/", "_")
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{slug}_{h}.txt"


def scrape_url(url: str) -> dict | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    text = trafilatura.extract(downloaded, include_links=True, include_tables=True)
    if not text or len(text.strip()) < 100:
        return None
    filename = url_to_filename(url)
    filepath = DATA_DIR_WEB / filename
    filepath.write_text(text, encoding="utf-8")
    return {"url": url, "path": str(filepath), "text_length": len(text)}


def scrape_urls(urls: list[str]) -> list[dict]:
    results = []
    for url in urls:
        result = scrape_url(url)
        if result:
            results.append(result)
    return results


def get_existing_web_files() -> list[Path]:
    return list(DATA_DIR_WEB.glob("*.txt"))

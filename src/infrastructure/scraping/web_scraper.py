from __future__ import annotations

import asyncio
import hashlib
from urllib.parse import urlparse

import trafilatura

from src.domain.models.scraped_page import ScrapedPage
from src.domain.ports.file_storage_port import FileStoragePort
from src.domain.ports.web_scraper_port import WebScraperPort
from src.infrastructure.storage.local_file_storage import LocalFileStorage


def url_to_filename(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path
    slug = slug.rstrip("/").replace("/", "_")
    h = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{slug}_{h}"


class WebScraper(WebScraperPort):
    def __init__(self, storage: FileStoragePort | None = None) -> None:
        self._storage = storage or LocalFileStorage()

    def scrape_url(self, url: str) -> ScrapedPage | None:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(downloaded, include_links=True, include_tables=True)
        if not text or len(text.strip()) < 100:
            return None
        filename = url_to_filename(url)
        content = text.encode("utf-8")
        asyncio.run(self._storage.save("web", filename, ".txt", content))
        filepath = self._storage.get_path("web", filename, ".txt")
        return ScrapedPage(url=url, path=str(filepath), text_length=len(text))

    def scrape_urls(self, urls: list[str]) -> list[ScrapedPage]:
        results: list[ScrapedPage] = []
        for url in urls:
            result = self.scrape_url(url)
            if result:
                results.append(result)
        return results


def scrape_urls(urls: list[str]) -> list[ScrapedPage]:
    scraper = WebScraper()
    return scraper.scrape_urls(urls)

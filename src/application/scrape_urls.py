from __future__ import annotations

from src.domain.ports.web_scraper_port import WebScraperPort


class ScrapeUrls:
    def __init__(self, scraper: WebScraperPort) -> None:
        self._scraper = scraper

    def execute(self, urls: list[str]) -> list[dict]:
        return self._scraper.scrape_urls(urls)

from __future__ import annotations

from src.domain.models.scraped_page import ScrapedPage
from src.domain.ports.web_scraper_port import WebScraperPort


class ScrapeUrls:
    def __init__(self, scraper: WebScraperPort) -> None:
        self._scraper = scraper

    def execute(self, urls: list[str]) -> list[ScrapedPage]:
        return self._scraper.scrape_urls(urls)

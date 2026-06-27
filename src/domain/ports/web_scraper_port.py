from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.models.scraped_page import ScrapedPage


class WebScraperPort(ABC):
    """Port for web scraping operations."""

    @abstractmethod
    def scrape_url(self, url: str) -> ScrapedPage | None: ...

    @abstractmethod
    def scrape_urls(self, urls: list[str]) -> list[ScrapedPage]: ...

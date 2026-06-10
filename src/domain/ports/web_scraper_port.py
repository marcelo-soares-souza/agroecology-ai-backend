from __future__ import annotations

from abc import ABC, abstractmethod


class WebScraperPort(ABC):
    """Port for web scraping operations."""

    @abstractmethod
    def scrape_url(self, url: str) -> dict | None: ...

    @abstractmethod
    def scrape_urls(self, urls: list[str]) -> list[dict]: ...

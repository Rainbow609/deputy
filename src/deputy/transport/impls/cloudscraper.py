"""CloudscraperTransport — bypasses Cloudflare JS challenges via cloudscraper."""

from __future__ import annotations

import importlib.util
import logging

from deputy.transport.chain import TransportError, TransportResult


class CloudscraperTransport:
    """Transport using cloudscraper to handle Cloudflare JS challenges."""

    name = "cloudscraper"
    available = True

    def __init__(self, browser: dict | None = None):
        self._browser = browser or {"browser": "chrome", "platform": "windows", "mobile": False}
        self._logger = logging.getLogger("deputy.transport.cloudscraper")
        if importlib.util.find_spec("cloudscraper") is None:
            self.available = False
            self._logger.debug("cloudscraper not installed; transport marked unavailable")

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        if not self.available:
            raise TransportError("cloudscraper not installed", retryable=False)
        import cloudscraper

        try:
            create = getattr(cloudscraper, "create_scraper", None) or cloudscraper.create_cloudScraper
            scraper = create(browser=self._browser)
            resp = scraper.get(url, timeout=timeout)
        except ImportError as e:
            raise TransportError("cloudscraper dependency missing", retryable=False) from e
        body = getattr(resp, "content", b"") or getattr(resp, "text", "")
        status = getattr(resp, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)

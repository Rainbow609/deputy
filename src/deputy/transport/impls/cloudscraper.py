"""CloudscraperTransport — bypasses Cloudflare JS challenges via cloudscraper."""

from __future__ import annotations

import logging

from deputy.transport.chain import TransportError, TransportResult


class CloudscraperTransport:
    """Transport using cloudscraper to handle Cloudflare JS challenges."""

    name = "cloudscraper"
    available = True

    def __init__(self, browser: dict | None = None):
        self._browser = browser or {"browser": "chrome", "platform": "windows", "mobile": False}
        self._logger = logging.getLogger("deputy.transport.cloudscraper")
        try:
            import cloudscraper  # noqa: F401
        except ImportError as e:
            raise TransportError("cloudscraper not installed", retryable=False) from e

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        try:
            import cloudscraper
        except ImportError as e:
            raise TransportError("cloudscraper not installed", retryable=False) from e

        try:
            create = getattr(cloudscraper, "create_scraper", None) or cloudscraper.create_cloudScraper
            scraper = create(browser=self._browser)
            resp = scraper.get(url, timeout=timeout)
        except ImportError as e:
            raise TransportError("cloudscraper dependency missing", retryable=False) from e
        body = getattr(resp, "content", b"") or getattr(resp, "text", "")
        status = getattr(resp, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)

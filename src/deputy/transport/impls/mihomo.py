"""MihomoTransport — uses the clash-meta User-Agent, often whitelisted by CDNs."""

from __future__ import annotations

import logging

from deputy.transport.chain import TransportError, TransportResult


class MihomoTransport:
    """Transport using the clash-meta User-Agent.

    Some subscription CDNs whitelist this UA so it acts as a low-cost first
    fallback before cloudscraper kicks in.
    """

    name = "clash-meta"
    available = True

    def __init__(self, user_agent: str = "clash-meta"):
        self._user_agent = user_agent
        self._logger = logging.getLogger("deputy.transport.mihomo")
        try:
            import requests  # noqa: F401
        except ImportError as e:
            raise TransportError("requests not installed", retryable=False) from e

    def _strip_flag_clash(self, url: str) -> str:
        """Strip ``flag=clash`` from the URL — the clash-meta UA already implies it."""
        if "flag=clash" not in url:
            return url
        return (
            url.replace("&flag=clash", "")
            .replace("?flag=clash&", "?")
            .replace("?flag=clash", "")
        )

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        import requests

        headers = {"User-Agent": self._user_agent}
        fetch_url = self._strip_flag_clash(url)
        session = requests.Session()
        resp = session.get(fetch_url, headers=headers, timeout=timeout)
        body = getattr(resp, "content", b"") or getattr(resp, "text", "")
        status = getattr(resp, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)

"""RequestsTransport — plain HTTP via the requests library with Chrome UA."""

from __future__ import annotations

import logging

from deputy.transport.chain import TransportError, TransportResult


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class RequestsTransport:
    """Transport using plain requests with a Chrome-like User-Agent."""

    name = "requests"
    available = True

    def __init__(self, user_agent: str | None = None):
        self._user_agent = user_agent
        self._logger = logging.getLogger("deputy.transport.requests")
        try:
            import requests  # noqa: F401
        except ImportError as e:
            raise TransportError("requests not installed", retryable=False) from e

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        import requests

        headers = {"User-Agent": self._user_agent or _DEFAULT_UA}
        session = requests.Session()
        resp = session.get(url, headers=headers, timeout=timeout)
        body = getattr(resp, "content", b"") or getattr(resp, "text", "")
        status = getattr(resp, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)

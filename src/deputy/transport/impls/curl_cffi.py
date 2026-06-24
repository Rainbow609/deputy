"""CurlCffiTransport / CurlCffiSafariTransport — TLS/HTTP fingerprint impersonation."""

from __future__ import annotations

import importlib.util
import logging

from deputy.transport.chain import TransportError, TransportResult


class CurlCffiTransport:
    """Transport using curl_cffi to impersonate Chrome TLS/HTTP fingerprint."""

    name = "curl_cffi"
    available = True

    def __init__(self, impersonate: str = "chrome120"):
        self._impersonate = impersonate
        self._logger = logging.getLogger("deputy.transport.curl_cffi")
        # Optional dependency: detect at construction time.
        if importlib.util.find_spec("curl_cffi") is None:
            self.available = False
            self._logger.debug("curl_cffi not installed; transport marked unavailable")

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        if not self.available:
            raise TransportError("curl_cffi not installed", retryable=False)
        from curl_cffi import requests as curl_requests

        resp = curl_requests.get(url, impersonate=self._impersonate, timeout=timeout)
        body = getattr(resp, "content", b"") or getattr(resp, "text", "")
        status = getattr(resp, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)


class CurlCffiSafariTransport(CurlCffiTransport):
    """Transport using curl_cffi Safari TLS/HTTP fingerprint."""

    name = "curl_cffi_safari"

    def __init__(self):
        super().__init__(impersonate="safari17_0")

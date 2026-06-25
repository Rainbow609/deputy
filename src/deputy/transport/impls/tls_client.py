"""TlsClientTransport — TLS fingerprint impersonation via tls-client (utls)."""

from __future__ import annotations

import importlib.util
import logging

from deputy.transport.chain import TransportError, TransportResult


class _TlsClientResponseAdapter:
    """Adapt tls-client responses to the subset of attributes we read."""

    def __init__(self, response):
        self._response = response

    def __getattr__(self, name):
        return getattr(self._response, name)


class TlsClientTransport:
    """Transport using tls-client (utls) with a Chrome fingerprint."""

    name = "tls_client"
    available = True

    def __init__(self, client_identifier: str = "chrome_120"):
        self._client_identifier = client_identifier
        self._logger = logging.getLogger("deputy.transport.tls_client")
        if importlib.util.find_spec("tls_client") is None:
            self.available = False
            self._logger.debug("tls_client not installed; transport marked unavailable")

    def fetch(self, url: str, *, timeout: int = 30) -> TransportResult:
        if not self.available:
            raise TransportError("tls_client not installed", retryable=False)
        import tls_client

        session = tls_client.Session(
            client_identifier=self._client_identifier,
            random_tls_extension_order=True,
        )
        resp = session.get(url, timeout_seconds=timeout)
        adapter = _TlsClientResponseAdapter(resp)
        body = getattr(adapter, "content", b"") or getattr(adapter, "text", "")
        status = getattr(adapter, "status_code", 200)
        return TransportResult(body=body, status=status, transport_name=self.name)

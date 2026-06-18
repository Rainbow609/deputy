"""HTTP transport chain for subscription fetching.

Implements a robust fallback chain: cloudscraper → requests → curl_cffi.
The chain rotates transports round-robin per attempt round (not "exhaust
transport A, then advance to B"), so each transport gets a fair chance.

This is a direct port of the mihomo-config TransportChain design, which has
proven effective at handling Cloudflare challenges and anti-bot systems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol


class TransportError(Exception):
    """Raised when a transport fails to fetch a URL.

    Args:
        message: Human-readable error.
        retryable: True if the chain should try the next transport.
        status_code: HTTP status if applicable.
    """

    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


@dataclass
class TransportResult:
    body: str | bytes
    status: int
    transport_name: str

    def text(self) -> str:
        if isinstance(self.body, bytes):
            return self.body.decode("utf-8", errors="replace")
        return self.body


class Transport(Protocol):
    """Protocol for a single transport implementation."""

    name: str

    def fetch(self, url: str, *, timeout: int = 10) -> TransportResult: ...


_RETRYABLE_STATUSES = {403, 502, 503, 504}


def _is_retryable_status(status: int) -> bool:
    return status in _RETRYABLE_STATUSES or status >= 500


class TransportChain:
    """Coordinated multi-transport fetcher with round-robin rotation.

    With max_attempts=N and K transports, attempts are distributed so that
    each transport gets roughly N/K tries. This guarantees later transports
    in the chain get a chance even when earlier ones fail repeatedly.
    """

    def __init__(self, transports: list[Transport], *, max_attempts: int = 4):
        if not transports:
            raise ValueError("transports must not be empty")
        self.transports = transports
        self.max_attempts = max_attempts
        self._logger = logging.getLogger("deputy.transport")

    def fetch(self, url: str, *, timeout: int = 10) -> TransportResult:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            transport = self.transports[attempt % len(self.transports)]
            try:
                result = transport.fetch(url, timeout=timeout)
                if _is_retryable_status(result.status):
                    self._logger.debug(
                        "retryable status from %s: %d", transport.name, result.status
                    )
                    last_error = TransportError(
                        f"status {result.status}", retryable=True, status_code=result.status
                    )
                    continue
                if result.status != 200:
                    raise TransportError(
                        f"status {result.status}", retryable=False, status_code=result.status
                    )
                return result
            except TransportError as e:
                last_error = e
                if not e.retryable:
                    raise
                self._logger.debug("transport %s failed: %s", transport.name, e)
                continue
        if last_error:
            raise TransportError(
                f"all transports failed: {last_error}", retryable=False
            ) from last_error
        raise TransportError("all transports failed without a captured error", retryable=False)
"""Transport abstraction for fetching subscription URLs with fallback.

Provides a chain of transport implementations (cloudscraper → requests →
curl_cffi → curl_cffi_safari → mihomo → tls_client) that rotate round-robin
across attempts with exponential backoff. Each transport may declare
``available = False`` if its optional dependency is missing, and the chain
will skip it automatically.

The chain shape mirrors mihomo-config's design but keeps backward-compatible
constructors that accept the legacy ``max_attempts`` keyword (mapped to
``max_total_attempts``) so existing tests continue to pass.
"""

from __future__ import annotations

import logging
import random
import time
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
    available: bool

    def fetch(self, url: str, *, timeout: int = 10) -> TransportResult: ...


_RETRYABLE_STATUSES = {403, 502, 503, 504}


def _is_retryable_status(status: int) -> bool:
    return status in _RETRYABLE_STATUSES or status >= 500


def _is_challenge(text: str) -> bool:
    """Detect Cloudflare challenge markers in a response body."""
    markers = [
        "cf-browser-verification",
        "__cf_chl_jschl_tk__",
        "Checking your browser",
        "Just a moment",
        "cf_challenge",
    ]
    lowered = text.lower()
    return any(m.lower() in lowered for m in markers)


class TransportChain:
    """Coordinated multi-transport fetcher with round-robin rotation.

    With ``max_attempts_per_transport=N`` and ``K`` transports, attempts are
    distributed so that each transport gets roughly N tries. The total number
    of attempts is capped by ``max_total_attempts``.

    Between full rounds the chain sleeps for ``_calculate_delay(round)``
    seconds (exponential backoff with jitter).
    """

    def __init__(
        self,
        transports: list[Transport],
        *,
        max_attempts_per_transport: int = 2,
        max_total_attempts: int | None = None,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        jitter_range: float = 0.5,
        sleep_fn=None,
        max_attempts: int | None = None,
    ):
        if not transports:
            raise ValueError("transports must not be empty")
        # Backward compatibility: legacy callers pass ``max_attempts=N`` to
        # bound the total number of attempts. Map it onto max_total_attempts.
        if max_attempts is not None:
            if max_total_attempts is None:
                max_total_attempts = max_attempts
            else:
                raise ValueError("pass only one of max_attempts / max_total_attempts")
        if max_total_attempts is None:
            max_total_attempts = max_attempts_per_transport * len(transports)
        if max_total_attempts < 1:
            raise ValueError("max_total_attempts must be >= 1")

        self.transports = list(transports)
        self.max_attempts_per_transport = max_attempts_per_transport
        self.max_total_attempts = max_total_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_range = jitter_range
        self.sleep_fn = sleep_fn or time.sleep
        self._logger = logging.getLogger("deputy.transport")

    def _calculate_delay(self, attempt: int) -> float:
        delay = self.base_delay * (2 ** attempt)
        if delay > self.max_delay:
            delay = self.max_delay
        delay += random.uniform(0, self.jitter_range)
        return delay

    def _available_transports(self) -> list[Transport]:
        available = [t for t in self.transports if getattr(t, "available", True) is not False]
        if not available:
            return list(self.transports)
        return available

    def fetch(self, url: str, *, timeout: int = 10) -> TransportResult:
        last_error: Exception | None = None
        available = self._available_transports()
        total_attempts = 0

        for round_idx in range(self.max_attempts_per_transport):
            progressed_in_round = False
            for transport in available:
                if total_attempts >= self.max_total_attempts:
                    break
                total_attempts += 1
                progressed_in_round = True
                try:
                    result = transport.fetch(url, timeout=timeout)
                except TransportError as e:
                    last_error = e
                    if not e.retryable:
                        raise
                    self._logger.debug("transport %s failed: %s", transport.name, e)
                    continue

                status = getattr(result, "status", 200)
                if status in _RETRYABLE_STATUSES or status >= 500:
                    self._logger.debug(
                        "retryable status from %s: %d", transport.name, status
                    )
                    last_error = TransportError(
                        f"status {status}", retryable=True, status_code=status
                    )
                    continue
                if status != 200:
                    raise TransportError(
                        f"status {status}", retryable=False, status_code=status
                    )
                # Detect Cloudflare challenge pages disguised as 200 responses.
                try:
                    if _is_challenge(result.text()):
                        last_error = TransportError(
                            "challenge page detected", retryable=True, status_code=status
                        )
                        self._logger.debug("challenge detected via %s", transport.name)
                        continue
                except Exception:
                    pass
                return result

            if not progressed_in_round:
                break
            if total_attempts >= self.max_total_attempts:
                break
            if round_idx + 1 < self.max_attempts_per_transport:
                delay = self._calculate_delay(round_idx)
                self.sleep_fn(delay)

        if last_error:
            raise TransportError(
                f"all transports failed: {last_error}", retryable=False
            ) from last_error
        raise TransportError("all transports failed without a captured error", retryable=False)

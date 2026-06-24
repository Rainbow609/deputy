"""Tests for TransportChain round-robin fallback behavior."""

from __future__ import annotations

import pytest

from deputy.transport.chain import (
    TransportChain,
    TransportError,
    TransportResult,
    _is_challenge,
    _is_retryable_status,
)


class FakeTransport:
    def __init__(self, name, body=None, *, raises=None, status=200):
        self.name = name
        self.body = body
        self.raises = raises
        self.status = status
        self.calls = 0

    def fetch(self, url, *, timeout=10):
        self.calls += 1
        if self.raises:
            raise self.raises
        return TransportResult(body=self.body, status=self.status, transport_name=self.name)


def test_chain_returns_first_successful_transport():
    a = FakeTransport("a", body="ok-a", status=200)
    b = FakeTransport("b", body="ok-b", status=200)
    chain = TransportChain([a, b], max_attempts=2)
    result = chain.fetch("https://x")
    assert result.body == "ok-a"
    assert result.transport_name == "a"


def test_chain_falls_back_on_5xx():
    a = FakeTransport("a", raises=TransportError("503", retryable=True))
    b = FakeTransport("b", body="ok-b", status=200)
    chain = TransportChain([a, b], max_attempts=3)
    result = chain.fetch("https://x")
    assert result.body == "ok-b"
    assert result.transport_name == "b"


def test_chain_rotates_round_robin_across_attempts():
    """With max_attempts=3 and 3 transports, the chain rotates per attempt,
    not exhaust-then-advance. This ensures curl_cffi gets a chance even when
    cloudscraper fails twice.
    """
    a = FakeTransport("a", raises=TransportError("fail", retryable=True))
    b = FakeTransport("b", raises=TransportError("fail", retryable=True))
    c = FakeTransport("c", body="ok-c", status=200)
    chain = TransportChain([a, b, c], max_attempts=3)
    result = chain.fetch("https://x")
    assert result.body == "ok-c"
    # a tried once, b tried once, c tried once = 3 total
    assert a.calls == 1
    assert b.calls == 1
    assert c.calls == 1


def test_chain_raises_when_all_transports_fail():
    a = FakeTransport("a", raises=TransportError("fail", retryable=True))
    b = FakeTransport("b", raises=TransportError("fail", retryable=True))
    chain = TransportChain([a, b], max_attempts=2)
    with pytest.raises(TransportError, match="all transports failed"):
        chain.fetch("https://x")


def test_chain_does_not_retry_4xx_other_than_403():
    """4xx errors (except 403) are client errors — no point retrying."""
    a = FakeTransport("a", body="bad", status=404)
    chain = TransportChain([a], max_attempts=3)
    with pytest.raises(TransportError, match="404"):
        chain.fetch("https://x")
    assert a.calls == 1  # did not retry


def test_chain_retries_on_403():
    a = FakeTransport("a", body="forbidden", status=403)
    b = FakeTransport("b", body="ok-b", status=200)
    chain = TransportChain([a, b], max_attempts=3)
    result = chain.fetch("https://x")
    assert result.body == "ok-b"


def test_is_retryable_status_classifies_codes():
    assert _is_retryable_status(403)
    assert _is_retryable_status(500)
    assert _is_retryable_status(502)
    assert _is_retryable_status(504)
    assert not _is_retryable_status(200)
    assert not _is_retryable_status(404)


def test_is_challenge_detects_cf_markers():
    assert _is_challenge("Just a moment... Cloudflare")
    assert _is_challenge("<html>cf-browser-verification</html>")
    assert not _is_challenge("<html>ok</html>")


def test_chain_skips_unavailable_transports():
    a = FakeTransport("a", raises=TransportError("missing", retryable=False))
    a.available = False
    b = FakeTransport("b", body="ok", status=200)
    chain = TransportChain([a, b], max_attempts=2)
    result = chain.fetch("https://x")
    assert result.transport_name == "b"
    assert a.calls == 0
    assert b.calls == 1


def test_chain_detects_challenge_in_200_body():
    a = FakeTransport("a", body="<html>Just a moment...</html>", status=200)
    b = FakeTransport("b", body="ok", status=200)
    chain = TransportChain([a, b], max_attempts=2)
    result = chain.fetch("https://x")
    assert result.body == "ok"

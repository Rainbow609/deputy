"""Tests for TCP probing — mirrors the legacy node_verifier tests."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from deputy.probing.tcp import (
    NodeVerifier,
    SingleProbeResult,
    classify_probe_failure,
    classify_failure,
    probe_family_value,
    resolve_addresses,
    tcp_check,
    tcp_probe,
)
from deputy.core.nodes import in_benchmark_range


def test_classify_failure_dns():
    assert classify_failure(exc=socket.gaierror("no such host")) == "dns-failed"


def test_classify_failure_timeout():
    assert classify_failure(exc=socket.timeout("timed out")) == "timeout"


def test_classify_failure_connection_refused():
    assert classify_failure(code=111) == "connection-refused"


def test_classify_failure_unreachable():
    assert classify_failure(code=113) == "unreachable"


def test_classify_failure_unknown():
    assert classify_failure() == "unknown-error"


def test_classify_probe_failure_alias_matches_legacy():
    """``classify_probe_failure`` is the mihomo-config name; ensure parity."""
    assert classify_probe_failure(exc=socket.gaierror("x")) == "dns-failed"
    assert classify_probe_failure(code=111) == "connection-refused"


def test_probe_family_value_resolves_names():
    import socket as _s

    assert probe_family_value("ipv4") == _s.AF_INET
    assert probe_family_value("ipv6") == _s.AF_INET6
    assert probe_family_value("auto") == _s.AF_UNSPEC


def test_in_benchmark_range_detects_198_18_and_198_19():
    assert in_benchmark_range("198.18.0.1")
    assert in_benchmark_range("198.19.255.254")
    assert not in_benchmark_range("198.20.0.1")
    assert not in_benchmark_range("1.1.1.1")
    assert not in_benchmark_range("not.an.ip.addr")
    assert not in_benchmark_range("")


def test_resolve_addresses_returns_unique_families(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, *a, **kw: [
            (2, 1, 6, "", ("1.1.1.1", 443)),
            (2, 1, 6, "", ("1.1.1.1", 443)),
            (10, 1, 6, "", ("::1", 443, 0, 0)),
        ],
    )
    addrs = resolve_addresses("example.com", 443, "auto")
    families = {a[0] for a in addrs}
    assert socket.AF_INET in families
    assert len(addrs) == 2  # IPv4 dedup


def test_verify_node_marks_alive_when_tcp_succeeds():
    verifier = NodeVerifier(timeout=1, retries=0, address_family="auto")
    node = {"name": "test", "server": "1.1.1.1", "port": 80, "type": "vmess"}
    with patch.object(
        verifier,
        "_tcp_check",
        return_value=SingleProbeResult(alive=True, latency_ms=42.0),
    ):
        result = verifier.verify_node(node)
    assert result.alive
    assert result.latency_ms == 42.0


def test_verify_node_marks_dead_when_endpoint_missing():
    verifier = NodeVerifier(timeout=1, retries=0, address_family="auto")
    node = {"name": "test", "type": "vmess"}
    result = verifier.verify_node(node)
    assert not result.alive
    assert result.failure_reason == "missing-endpoint"


def test_tcp_check_returns_missing_endpoint_for_blank_node():
    proxy, ok, info = tcp_check({"name": "x"}, timeout=1)
    assert ok is False
    assert info == "missing-endpoint"


def test_tcp_probe_collects_alive_and_dead(monkeypatch):
    """Use a mock transport — simulate one success, one failure."""

    def fake_tcp_check(proxy, timeout, retries, address_family):
        if proxy.get("name") == "alive":
            return proxy, True, {"avg_ms": 50.0, "min_ms": 50.0, "max_ms": 50.0,
                                 "variance": 0.0, "jitter": 0.0, "samples": 1}
        return proxy, False, "connection-refused"

    monkeypatch.setattr("deputy.probing.tcp.tcp_check", fake_tcp_check)
    proxies = [
        {"name": "alive", "server": "1.1.1.1", "port": 443, "type": "vmess"},
        {"name": "dead", "server": "2.2.2.2", "port": 443, "type": "vmess"},
    ]
    result = tcp_probe(proxies, timeout=1, concurrency=2)
    assert {p["name"] for p in result.alive} == {"alive"}
    assert len(result.dead) == 1
    assert result.dead[0][0]["name"] == "dead"
    assert result.stats_by_name["alive"]["avg_ms"] == 50.0

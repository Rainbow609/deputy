import socket
import time
import pytest
from unittest.mock import patch
from scripts.node_verifier import (
    NodeVerifier,
    ProbeResult,
    classify_failure,
    resolve_addresses,
)


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


def test_verify_node_marks_alive_when_tcp_succeeds():
    verifier = NodeVerifier(timeout=1, retries=0, address_family="auto")
    node = {"name": "test", "server": "1.1.1.1", "port": 80, "type": "vmess"}
    with patch.object(verifier, "_tcp_check", return_value=ProbeResult(alive=True, latency_ms=42.0)):
        result = verifier.verify_node(node)
    assert result.alive
    assert result.latency_ms == 42.0


def test_verify_node_marks_dead_when_endpoint_missing():
    verifier = NodeVerifier(timeout=1, retries=0, address_family="auto")
    node = {"name": "test", "type": "vmess"}  # no server/port
    result = verifier.verify_node(node)
    assert not result.alive
    assert result.failure_reason == "missing-endpoint"
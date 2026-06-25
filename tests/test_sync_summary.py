"""Tests for the probe-JSON + summary helpers."""

from __future__ import annotations

import json

import pytest

from deputy.probing.tcp import ProbeResult
from deputy.utils.summary import (
    build_probe_json_payload,
    fetch_status_rows,
    print_latency_overview,
    region_counts,
)
from deputy.sources.subscription import SubscriptionFetchResult


def _probe_result():
    return ProbeResult(
        alive=[
            {"name": "alive-1", "server": "1.1.1.1", "port": 443, "type": "vmess"},
            {"name": "alive-2", "server": "2.2.2.2", "port": 443, "type": "vmess"},
        ],
        dead=[({"name": "dead-1", "server": "3.3.3.3", "port": 443, "type": "vmess"},
               "connection-refused")],
        stats_by_name={
            "alive-1": {"avg_ms": 100.0, "min_ms": 80.0, "max_ms": 120.0,
                         "variance": 200.0, "jitter": 5.0, "samples": 3},
            "alive-2": {"avg_ms": 50.0, "min_ms": 40.0, "max_ms": 60.0,
                         "variance": 100.0, "jitter": 2.0, "samples": 3},
        },
    )


def test_build_probe_json_payload_shape():
    filtered = [{"name": "alive-1"}, {"name": "dead-1"}]
    payload = json.loads(build_probe_json_payload(filtered, _probe_result()))
    assert payload["phase"] == "tcp_probe"
    assert payload["total"] == 2
    assert payload["alive"] == 2
    assert {a["name"] for a in payload["alive_nodes"]} == {"alive-1", "alive-2"}
    assert payload["dead"] == [{"name": "dead-1", "reason": "connection-refused"}]
    assert payload["alive_nodes"][0]["avg_ms"] in (100.0, 50.0)


def test_print_latency_overview_does_not_crash_when_empty(capsys):
    print_latency_overview({})
    out = capsys.readouterr().out
    assert out == ""


def test_print_latency_overview_emits_summary(capsys):
    print_latency_overview({
        "a": {"avg_ms": 50},
        "b": {"avg_ms": 100},
    })
    out = capsys.readouterr().out
    assert "avg=75.0ms" in out or "avg=75ms" in out
    assert "nodes=2" in out


def test_region_counts_buckets_by_name_pattern():
    counts = region_counts(["香港-01", "JP-Tokyo-1", "US-LA", "新加坡-SG1", "Taiwan-TW1", "Other"])
    assert counts["hk"] == 1
    assert counts["jp"] == 1
    assert counts["us"] == 1
    assert counts["sg"] == 1
    assert counts["tw"] == 1


def test_region_counts_zero_when_empty():
    counts = region_counts([])
    assert all(v == 0 for v in counts.values())


def test_fetch_status_rows_handles_unknown_status():
    rows = fetch_status_rows([SubscriptionFetchResult("src", [], "weird", "none")])
    assert "weird" in rows[0][1]

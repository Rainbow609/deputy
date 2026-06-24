"""Tests for quality metrics and release-notes builder."""

from __future__ import annotations

from deputy.utils.quality import (
    compute_latency_stats,
    compute_survival_rate,
)
from deputy.utils.summary import build_release_notes, fetch_status_rows
from deputy.sources.subscription import SubscriptionFetchResult


def test_survival_rate_all_alive():
    rate = compute_survival_rate(alive=8, total=10)
    assert rate == 80.0


def test_survival_rate_zero_total():
    assert compute_survival_rate(alive=0, total=0) == 0.0


def test_latency_stats_basic():
    latencies = [10, 20, 30, 40, 50]
    stats = compute_latency_stats(latencies)
    assert stats["avg"] == 30.0
    assert stats["min"] == 10
    assert stats["max"] == 50
    assert stats["p50"] == 30
    assert stats["p95"] == 50


def test_latency_stats_empty():
    stats = compute_latency_stats([])
    assert stats["avg"] == 0
    assert stats["min"] is None
    assert stats["max"] is None


def test_latency_stats_drops_none_values():
    stats = compute_latency_stats([10, None, 20, None, 30])
    assert stats["avg"] == 20.0


def test_format_release_notes_includes_summary():
    notes = build_release_notes(
        version="v2024-06-18-120000",
        stats={
            "total": 50, "alive": 40, "survival_rate": 80.0,
            "latency_avg": 120, "latency_min": 30, "latency_max": 400,
            "added": 5, "removed": 2,
        },
        failed_sources=[("星链云", "timeout")],
    )
    assert "v2024-06-18-120000" in notes
    assert "50" in notes
    assert "40" in notes
    assert "80.0%" in notes or "80%" in notes
    assert "星链云" in notes
    assert "timeout" in notes


def test_fetch_status_rows_marks_fresh_updated():
    rows = fetch_status_rows([SubscriptionFetchResult("src", [{"name": "a"}],
                                                      "fresh", "updated")])
    assert rows[0][0] == "src"
    assert "已更新" in rows[0][1]
    assert rows[0][2] == "1"


def test_fetch_status_rows_marks_fallback():
    rows = fetch_status_rows([SubscriptionFetchResult("src", [{"name": "a"}],
                                                      "fallback", "fallback",
                                                      "2024-06-18T00:00:00Z")])
    assert "缓存" in rows[0][1]
    assert "2024-06-18T00:00:00Z" in rows[0][2]


def test_fetch_status_rows_marks_failed():
    rows = fetch_status_rows([SubscriptionFetchResult("src", [], "failed", "none")])
    assert "失败" in rows[0][1]
    assert rows[0][2] == "0"
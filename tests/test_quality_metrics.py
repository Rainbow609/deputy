from scripts.quality_metrics import (
    compute_survival_rate,
    compute_latency_stats,
    format_release_notes,
)


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
    assert stats["p95"] == 50  # with 5 samples, p95 is the max


def test_latency_stats_empty():
    stats = compute_latency_stats([])
    assert stats["avg"] == 0
    assert stats["min"] is None
    assert stats["max"] is None


def test_format_release_notes_includes_summary():
    notes = format_release_notes(
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
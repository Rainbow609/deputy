"""Tests for the probe-JSON + summary helpers."""

from __future__ import annotations

import json

import pytest

from deputy.probing.tcp import ProbeResult
from deputy.utils.summary import (
    build_probe_json_payload,
    build_verification_json_payload,
    fetch_status_rows,
    print_latency_overview,
    region_counts,
    summarize_verification_assessments,
)
from deputy.probing.verification import HistoryRecord, VerificationAssessment
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


def test_build_verification_json_payload_shape():
    assessments = {
        "vmess|1.1.1.1|443": VerificationAssessment(
            node_key="vmess|1.1.1.1|443",
            proxy_name="alive-1",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=["cn-tcp-ok", "mihomo-delay-ok"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "itdog",
                    "attempted_providers": ["itdog"],
                    "sample_count": 3,
                    "success_count": 2,
                    "samples": [{"provider": "itdog", "location": "辽宁大连电信", "ok": True}],
                },
                "mihomo_delay": {"ok": True, "delay_ms": 123},
            },
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        )
    }
    payload = json.loads(build_verification_json_payload(assessments, filtered_count=2))
    assert payload["phase"] == "verification"
    assert payload["total"] == 2
    assert payload["overview"]["cn_sample_count"] == 3
    assert payload["overview"]["cn_provider"] == "itdog"
    assert payload["overview"]["cn_attempted_providers"] == ["itdog"]
    assert payload["mihomo_overview"]["tested_nodes"] == 1
    assert payload["mihomo_overview"]["success_count"] == 1
    assert payload["mihomo_overview"]["failure_count"] == 0
    assert payload["mihomo_overview"]["timeout_count"] == 0
    assert payload["mihomo_overview"]["success_rate"] == 100.0
    assert payload["nodes"][0]["name"] == "alive-1"
    assert payload["nodes"][0]["status"] == "reachable"
    assert payload["nodes"][0]["block_confidence"] == 0


def test_summarize_verification_assessments_aggregates_cn_probe_signal():
    assessments = {
        "vmess|1.1.1.1|443": VerificationAssessment(
            node_key="vmess|1.1.1.1|443",
            proxy_name="alive-1",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=["cn-tcp-ok", "mihomo-delay-ok"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "itdog",
                    "attempted_providers": ["itdog"],
                    "sample_count": 3,
                    "success_count": 2,
                    "timeout_count": 1,
                    "reset_count": 0,
                    "refused_count": 0,
                    "samples": [
                        {"provider": "itdog", "location": "辽宁大连电信", "ok": True},
                        {"provider": "itdog", "location": "江苏镇江电信", "ok": True},
                        {"provider": "itdog", "location": "湖南长沙电信", "ok": False},
                    ],
                },
                "mihomo_delay": {"ok": True, "delay_ms": 120},
            },
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        ),
        "vmess|2.2.2.2|443": VerificationAssessment(
            node_key="vmess|2.2.2.2|443",
            proxy_name="alive-2",
            status="suspected_gfw_blocked",
            block_confidence=80,
            policy_action="keep",
            reasons=["cn-tcp-all-failed"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "itdog",
                    "attempted_providers": ["itdog", "noop"],
                    "sample_count": 3,
                    "success_count": 0,
                    "timeout_count": 2,
                    "reset_count": 1,
                    "refused_count": 0,
                    "samples": [
                        {"provider": "itdog", "location": "辽宁大连电信", "ok": False},
                        {"provider": "itdog", "location": "江苏镇江电信", "ok": False},
                        {"provider": "itdog", "location": "湖南长沙电信", "ok": False},
                    ],
                },
                "mihomo_delay": {"ok": False, "delay_ms": None, "failure_reason": "timeout"},
            },
            history=HistoryRecord("suspected_gfw_blocked", 1, 80, "2026-06-29T00:00:00Z"),
        ),
    }

    overview = summarize_verification_assessments(assessments)
    assert overview["cn_provider"] == "itdog"
    assert overview["cn_attempted_providers"] == ["itdog", "noop"]
    assert overview["cn_nodes"] == 2
    assert overview["cn_sample_count"] == 6
    assert overview["cn_success_count"] == 2
    assert overview["cn_timeout_count"] == 3
    assert overview["cn_reset_count"] == 1
    assert overview["cn_refused_count"] == 0
    assert overview["cn_success_rate"] == 33.3
    assert overview["mihomo_tested_nodes"] == 2
    assert overview["mihomo_success_count"] == 1
    assert overview["mihomo_failure_count"] == 1
    assert overview["mihomo_timeout_count"] == 1
    assert overview["mihomo_success_rate"] == 50.0


def test_summarize_verification_assessments_counts_sample_provider_per_node():
    assessments = {
        "vmess|1.1.1.1|443": VerificationAssessment(
            node_key="vmess|1.1.1.1|443",
            proxy_name="alive-1",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=["cn-tcp-ok"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "",
                    "attempted_providers": ["itdog"],
                    "sample_count": 1,
                    "success_count": 1,
                    "samples": [{"provider": "itdog", "location": "辽宁大连电信", "ok": True}],
                }
            },
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        ),
        "vmess|2.2.2.2|443": VerificationAssessment(
            node_key="vmess|2.2.2.2|443",
            proxy_name="alive-2",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=["cn-tcp-ok"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "",
                    "attempted_providers": ["boce"],
                    "sample_count": 1,
                    "success_count": 1,
                    "samples": [{"provider": "boce", "location": "江苏宿迁联通", "ok": True}],
                }
            },
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        ),
        "vmess|3.3.3.3|443": VerificationAssessment(
            node_key="vmess|3.3.3.3|443",
            proxy_name="alive-3",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=["cn-tcp-ok"],
            signal_summary={
                "cn_tcp": {
                    "source_provider": "",
                    "attempted_providers": ["boce"],
                    "sample_count": 1,
                    "success_count": 1,
                    "samples": [{"provider": "boce", "location": "湖南长沙移动", "ok": True}],
                }
            },
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        ),
    }

    overview = summarize_verification_assessments(assessments)
    assert overview["cn_provider"] == "boce"
    assert overview["cn_attempted_providers"] == ["boce", "itdog"]


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

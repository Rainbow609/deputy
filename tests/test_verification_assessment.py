"""Tests for multi-signal verification assessment and history."""

from __future__ import annotations

from pathlib import Path

from deputy.probing.verification import (
    ChinaProbeSample,
    ChinaProbeSummary,
    HistoryRecord,
    VerificationAssessment,
    VerificationClassifierConfig,
    assess_node,
    apply_policy,
    build_node_key,
    load_history,
    save_history,
)


def _proxy(name: str = "node-1") -> dict:
    return {"name": name, "type": "vmess", "server": "1.1.1.1", "port": 443}


def _cn_summary(*, samples: int, success: int, timeout: int = 0, reset: int = 0, refused: int = 0) -> ChinaProbeSummary:
    return ChinaProbeSummary(
        samples=[
            ChinaProbeSample(
                provider="mock",
                location=f"cn-{idx}",
                ok=idx < success,
                latency_ms=80.0 if idx < success else None,
                failure_reason=None if idx < success else "timeout",
            )
            for idx in range(samples)
        ],
        sample_count=samples,
        success_count=success,
        timeout_count=timeout,
        reset_count=reset,
        refused_count=refused,
    )


def test_assess_service_down_when_control_tcp_fails():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=False,
        control_failure_reason="timeout",
        cn_summary=_cn_summary(samples=3, success=0, timeout=3),
        mihomo_delay_ok=False,
        mihomo_delay_ms=None,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "service_down"
    assert assessment.block_confidence == 0


def test_assess_suspected_gfw_on_first_failed_round():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=3, success=0, timeout=3),
        mihomo_delay_ok=False,
        mihomo_delay_ms=None,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "suspected_gfw_blocked"
    assert assessment.block_confidence == 80


def test_assess_upgrades_to_blocked_confirmed_after_history_window():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=3, success=0, timeout=2, reset=1),
        mihomo_delay_ok=False,
        mihomo_delay_ms=None,
        classifier=VerificationClassifierConfig(confirm_after_runs=3),
        history_record=HistoryRecord(
            last_status="suspected_gfw_blocked",
            consecutive_suspected_runs=2,
            last_block_confidence=80,
            last_seen_at="2026-06-29T00:00:00Z",
        ),
    )
    assert assessment.status == "blocked_confirmed"
    assert assessment.block_confidence == 100
    assert assessment.history.consecutive_suspected_runs == 3


def test_assess_reachable_when_cn_and_mihomo_succeed():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=3, success=2),
        mihomo_delay_ok=True,
        mihomo_delay_ms=123,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "reachable"
    assert assessment.block_confidence == 0


def test_assess_protocol_unhealthy_when_cn_succeeds_but_mihomo_fails():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=3, success=2),
        mihomo_delay_ok=False,
        mihomo_delay_ms=None,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "protocol_unhealthy"


def test_assess_reachable_unstable_when_cn_samples_insufficient_but_mihomo_ok():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=2, success=0),
        mihomo_delay_ok=True,
        mihomo_delay_ms=111,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "reachable_unstable"


def test_assess_unknown_when_cn_samples_insufficient_and_no_mihomo_success():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=2, success=0),
        mihomo_delay_ok=False,
        mihomo_delay_ms=None,
        classifier=VerificationClassifierConfig(),
        history_record=None,
    )
    assert assessment.status == "unknown"


def test_assess_respects_custom_cn_thresholds():
    assessment = assess_node(
        proxy=_proxy(),
        control_tcp_ok=True,
        control_failure_reason=None,
        cn_summary=_cn_summary(samples=3, success=2),
        mihomo_delay_ok=True,
        mihomo_delay_ms=100,
        classifier=VerificationClassifierConfig(),
        history_record=None,
        min_vantages=4,
        min_success_vantages=3,
    )
    assert assessment.status == "reachable_unstable"


def test_apply_policy_handles_all_modes():
    assessments = {
        "a": VerificationAssessment(
            node_key="a",
            proxy_name="a",
            status="reachable",
            block_confidence=0,
            policy_action="keep",
            reasons=[],
            signal_summary={},
            history=HistoryRecord("reachable", 0, 0, "2026-06-29T00:00:00Z"),
        ),
        "b": VerificationAssessment(
            node_key="b",
            proxy_name="b",
            status="suspected_gfw_blocked",
            block_confidence=80,
            policy_action="keep",
            reasons=[],
            signal_summary={},
            history=HistoryRecord("suspected_gfw_blocked", 1, 80, "2026-06-29T00:00:00Z"),
        ),
        "c": VerificationAssessment(
            node_key="c",
            proxy_name="c",
            status="blocked_confirmed",
            block_confidence=90,
            policy_action="keep",
            reasons=[],
            signal_summary={},
            history=HistoryRecord("blocked_confirmed", 3, 90, "2026-06-29T00:00:00Z"),
        ),
    }
    proxies = [{"name": "a"}, {"name": "b"}, {"name": "c"}]

    kept_mark, actions_mark = apply_policy(proxies, assessments, "mark")
    kept_confirmed, actions_confirmed = apply_policy(proxies, assessments, "exclude_confirmed")
    kept_suspected, actions_suspected = apply_policy(proxies, assessments, "exclude_suspected")

    assert [p["name"] for p in kept_mark] == ["a", "b", "c"]
    assert actions_mark["c"] == "keep"
    assert [p["name"] for p in kept_confirmed] == ["a", "b"]
    assert actions_confirmed["c"] == "exclude"
    assert [p["name"] for p in kept_suspected] == ["a"]
    assert actions_suspected["b"] == "exclude"


def test_history_round_trip(tmp_path: Path):
    history_path = tmp_path / "verification-history.json"
    key = build_node_key(_proxy())
    save_history(
        history_path,
        {
            key: HistoryRecord(
                last_status="suspected_gfw_blocked",
                consecutive_suspected_runs=2,
                last_block_confidence=80,
                last_seen_at="2026-06-29T00:00:00Z",
            )
        },
    )
    loaded = load_history(history_path)
    assert loaded[key].consecutive_suspected_runs == 2

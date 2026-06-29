"""Aggregate multi-signal node verification and policy decisions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deputy.probing.cn import ChinaProbeProvider, NoopChinaProbeProvider
from deputy.probing.health import HealthCheckResult, MihomoDelayChecker


VALID_STATUSES = {
    "reachable",
    "reachable_unstable",
    "protocol_unhealthy",
    "suspected_gfw_blocked",
    "blocked_confirmed",
    "service_down",
    "unknown",
}
VALID_FILTER_MODES = {"mark", "exclude_confirmed", "exclude_suspected"}


@dataclass(frozen=True)
class ChinaProbeConfig:
    enabled: bool = False
    provider: str = "noop"
    min_vantages: int = 3
    min_success_vantages: int = 2
    timeout: int = 5
    stale_after_seconds: int = 600


@dataclass(frozen=True)
class ProbeHealthConfig:
    enabled: bool = False
    kind: str = "mihomo_delay"
    controller_url: str = "http://127.0.0.1:9093"
    secret: str = ""
    test_url: str = "https://www.gstatic.com/generate_204"
    timeout_ms: int = 10_000
    expected: str = "200,204"


@dataclass(frozen=True)
class VerificationClassifierConfig:
    confirm_after_runs: int = 3
    filter_mode: str = "mark"
    history_path: str = ""


@dataclass(frozen=True)
class ChinaProbeSample:
    provider: str
    location: str
    ok: bool
    latency_ms: float | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class ChinaProbeSummary:
    samples: list[ChinaProbeSample] = field(default_factory=list)
    source_provider: str = ""
    attempted_providers: list[str] = field(default_factory=list)
    sample_count: int = 0
    success_count: int = 0
    timeout_count: int = 0
    reset_count: int = 0
    refused_count: int = 0

    @classmethod
    def empty(cls) -> "ChinaProbeSummary":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_provider": self.source_provider,
            "attempted_providers": self.attempted_providers,
            "sample_count": self.sample_count,
            "success_count": self.success_count,
            "timeout_count": self.timeout_count,
            "reset_count": self.reset_count,
            "refused_count": self.refused_count,
            "samples": [asdict(sample) for sample in self.samples],
        }


@dataclass(frozen=True)
class HistoryRecord:
    last_status: str
    consecutive_suspected_runs: int
    last_block_confidence: int
    last_seen_at: str


@dataclass(frozen=True)
class VerificationAssessment:
    node_key: str
    proxy_name: str
    status: str
    block_confidence: int
    policy_action: str
    reasons: list[str]
    signal_summary: dict[str, Any]
    history: HistoryRecord

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_key": self.node_key,
            "name": self.proxy_name,
            "status": self.status,
            "block_confidence": self.block_confidence,
            "policy_action": self.policy_action,
            "reasons": self.reasons,
            "signal_summary": self.signal_summary,
            "history": asdict(self.history),
        }


def build_node_key(proxy: dict) -> str:
    return f"{proxy.get('type', '')}|{proxy.get('server', '')}|{proxy.get('port', '')}"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_history(path: Path) -> dict[str, HistoryRecord]:
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    records: dict[str, HistoryRecord] = {}
    for key, raw in payload.items():
        records[key] = HistoryRecord(
            last_status=raw.get("last_status", "unknown"),
            consecutive_suspected_runs=int(raw.get("consecutive_suspected_runs", 0)),
            last_block_confidence=int(raw.get("last_block_confidence", 0)),
            last_seen_at=raw.get("last_seen_at", ""),
        )
    return records


def save_history(path: Path, history: dict[str, HistoryRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: asdict(record) for key, record in history.items()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_history(status: str, prior: HistoryRecord | None, confidence: int) -> HistoryRecord:
    previous_runs = prior.consecutive_suspected_runs if prior else 0
    consecutive = previous_runs + 1 if status in {"suspected_gfw_blocked", "blocked_confirmed"} else 0
    return HistoryRecord(
        last_status=status,
        consecutive_suspected_runs=consecutive,
        last_block_confidence=confidence,
        last_seen_at=utc_now_iso(),
    )


def assess_node(
    *,
    proxy: dict,
    control_tcp_ok: bool,
    control_failure_reason: str | None,
    cn_summary: ChinaProbeSummary,
    mihomo_delay_ok: bool,
    mihomo_delay_ms: int | None,
    classifier: VerificationClassifierConfig,
    history_record: HistoryRecord | None,
    min_vantages: int = 3,
    min_success_vantages: int = 2,
) -> VerificationAssessment:
    node_key = build_node_key(proxy)
    reasons: list[str] = []
    confidence = 0

    if not control_tcp_ok:
        reasons.append(control_failure_reason or "control-tcp-failed")
        status = "service_down"
        history = _next_history(status, history_record, confidence)
        return VerificationAssessment(
            node_key=node_key,
            proxy_name=proxy.get("name", ""),
            status=status,
            block_confidence=confidence,
            policy_action="keep",
            reasons=reasons,
            signal_summary={
                "control_tcp": {"ok": False, "failure_reason": control_failure_reason},
                "cn_tcp": cn_summary.to_dict(),
                "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
            },
            history=history,
        )

    if cn_summary.sample_count < 1:
        if mihomo_delay_ok:
            status = "reachable_unstable"
            reasons.append("control-tcp-ok")
            reasons.append("mihomo-delay-ok")
        else:
            status = "unknown"
            reasons.append("cn-samples-missing")
        history = _next_history(status, history_record, confidence)
        return VerificationAssessment(
            node_key=node_key,
            proxy_name=proxy.get("name", ""),
            status=status,
            block_confidence=confidence,
            policy_action="keep",
            reasons=reasons,
            signal_summary={
                "control_tcp": {"ok": True},
                "cn_tcp": cn_summary.to_dict(),
                "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
            },
            history=history,
        )

    if cn_summary.sample_count < min_vantages:
        status = "reachable_unstable" if mihomo_delay_ok else "unknown"
        reasons.append("cn-samples-insufficient")
        if mihomo_delay_ok:
            reasons.append("mihomo-delay-ok")
        history = _next_history(status, history_record, confidence)
        return VerificationAssessment(
            node_key=node_key,
            proxy_name=proxy.get("name", ""),
            status=status,
            block_confidence=confidence,
            policy_action="keep",
            reasons=reasons,
            signal_summary={
                "control_tcp": {"ok": True},
                "cn_tcp": cn_summary.to_dict(),
                "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
            },
            history=history,
        )

    if cn_summary.success_count >= min_success_vantages:
        status = "reachable" if mihomo_delay_ok else "protocol_unhealthy"
        reasons.append("cn-tcp-ok")
        reasons.append("mihomo-delay-ok" if mihomo_delay_ok else "mihomo-delay-failed")
        history = _next_history(status, history_record, confidence)
        return VerificationAssessment(
            node_key=node_key,
            proxy_name=proxy.get("name", ""),
            status=status,
            block_confidence=confidence,
            policy_action="keep",
            reasons=reasons,
            signal_summary={
                "control_tcp": {"ok": True},
                "cn_tcp": cn_summary.to_dict(),
                "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
            },
            history=history,
        )

    if cn_summary.success_count == 0:
        confidence = 60
        reasons.append("cn-tcp-all-failed")
        if cn_summary.sample_count and cn_summary.timeout_count / cn_summary.sample_count >= 0.6:
            confidence += 10
            reasons.append("cn-timeout-majority")
        if cn_summary.reset_count + cn_summary.refused_count > 0:
            confidence += 10
            reasons.append("cn-reset-or-refused")
        if not mihomo_delay_ok:
            confidence += 10
            reasons.append("mihomo-delay-failed")
        if history_record and history_record.last_status in {"suspected_gfw_blocked", "blocked_confirmed"}:
            confidence += 10
            reasons.append("prior-suspected")
        prior_runs = history_record.consecutive_suspected_runs if history_record else 0
        if prior_runs >= 2:
            confidence += 10
            reasons.append("consecutive-suspected-runs")
        confidence = min(confidence, 100)
        projected_runs = prior_runs + 1
        status = (
            "blocked_confirmed"
            if projected_runs >= classifier.confirm_after_runs and confidence >= 85
            else "suspected_gfw_blocked"
        )
        history = _next_history(status, history_record, confidence)
        return VerificationAssessment(
            node_key=node_key,
            proxy_name=proxy.get("name", ""),
            status=status,
            block_confidence=confidence,
            policy_action="keep",
            reasons=reasons,
            signal_summary={
                "control_tcp": {"ok": True},
                "cn_tcp": cn_summary.to_dict(),
                "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
            },
            history=history,
        )

    status = "reachable_unstable" if cn_summary.success_count > 0 else "unknown"
    reasons.append("cn-results-mixed")
    history = _next_history(status, history_record, confidence)
    return VerificationAssessment(
        node_key=node_key,
        proxy_name=proxy.get("name", ""),
        status=status,
        block_confidence=confidence,
        policy_action="keep",
        reasons=reasons,
        signal_summary={
            "control_tcp": {"ok": True},
            "cn_tcp": cn_summary.to_dict(),
            "mihomo_delay": {"ok": mihomo_delay_ok, "delay_ms": mihomo_delay_ms},
        },
        history=history,
    )


def assess_nodes(
    proxies: list[dict],
    probe_result,
    cn_config: ChinaProbeConfig | None = None,
    health_config: ProbeHealthConfig | None = None,
    classifier: VerificationClassifierConfig | None = None,
    history: dict[str, HistoryRecord] | None = None,
    cn_provider: ChinaProbeProvider | None = None,
    health_checker: MihomoDelayChecker | None = None,
) -> dict[str, VerificationAssessment]:
    cn_config = cn_config or ChinaProbeConfig()
    health_config = health_config or ProbeHealthConfig()
    classifier = classifier or VerificationClassifierConfig()
    cn_provider = cn_provider or NoopChinaProbeProvider()
    health_checker = health_checker or MihomoDelayChecker()
    history = history or {}

    dead_by_key = {build_node_key(proxy): reason for proxy, reason in probe_result.dead}
    assessments: dict[str, VerificationAssessment] = {}

    for proxy in proxies:
        node_key = build_node_key(proxy)
        control_ok = node_key not in dead_by_key
        cn_summary = cn_provider.probe(proxy, cn_config) if cn_config.enabled else ChinaProbeSummary.empty()
        health_result = (
            health_checker.check(proxy, health_config)
            if control_ok and health_config.enabled
            else HealthCheckResult(ok=False, failure_reason="health-disabled")
        )
        assessments[node_key] = assess_node(
            proxy=proxy,
            control_tcp_ok=control_ok,
            control_failure_reason=dead_by_key.get(node_key),
            cn_summary=cn_summary,
            mihomo_delay_ok=health_result.ok,
            mihomo_delay_ms=health_result.delay_ms,
            classifier=classifier,
            history_record=history.get(node_key),
            min_vantages=cn_config.min_vantages,
            min_success_vantages=cn_config.min_success_vantages,
        )
    return assessments


def _with_policy_action(assessment: VerificationAssessment, action: str) -> VerificationAssessment:
    return VerificationAssessment(
        node_key=assessment.node_key,
        proxy_name=assessment.proxy_name,
        status=assessment.status,
        block_confidence=assessment.block_confidence,
        policy_action=action,
        reasons=assessment.reasons,
        signal_summary=assessment.signal_summary,
        history=assessment.history,
    )


def _coerce_assessment(node_key: str, raw: VerificationAssessment | dict[str, Any]) -> VerificationAssessment:
    if isinstance(raw, VerificationAssessment):
        return raw
    history_raw = raw.get("history", {})
    return VerificationAssessment(
        node_key=node_key,
        proxy_name=raw.get("proxy_name") or raw.get("name", node_key),
        status=raw.get("status", "unknown"),
        block_confidence=int(raw.get("block_confidence", 0)),
        policy_action=raw.get("policy_action", "keep"),
        reasons=list(raw.get("reasons", [])),
        signal_summary=dict(raw.get("signal_summary", {})),
        history=HistoryRecord(
            last_status=history_raw.get("last_status", raw.get("status", "unknown")),
            consecutive_suspected_runs=int(history_raw.get("consecutive_suspected_runs", 0)),
            last_block_confidence=int(history_raw.get("last_block_confidence", raw.get("block_confidence", 0))),
            last_seen_at=history_raw.get("last_seen_at", ""),
        ),
    )


def _find_assessment_for_proxy(
    proxy: dict,
    assessments: dict[str, VerificationAssessment | dict[str, Any]],
) -> tuple[str, VerificationAssessment]:
    node_key = build_node_key(proxy)
    if node_key != "||" and node_key in assessments:
        return node_key, _coerce_assessment(node_key, assessments[node_key])

    proxy_name = proxy.get("name", "")
    for key, raw in assessments.items():
        assessment = _coerce_assessment(key, raw)
        if assessment.proxy_name == proxy_name:
            return key, assessment
    raise KeyError(node_key)


def apply_policy(
    proxies: list[dict],
    assessments: dict[str, VerificationAssessment | dict[str, Any]],
    filter_mode: str,
) -> tuple[list[dict], dict[str, str]]:
    kept: list[dict] = []
    actions: dict[str, str] = {}
    for proxy in proxies:
        node_key, assessment = _find_assessment_for_proxy(proxy, assessments)
        exclude = False
        if filter_mode == "exclude_confirmed" and assessment.status == "blocked_confirmed":
            exclude = True
        elif filter_mode == "exclude_suspected" and assessment.status in {"suspected_gfw_blocked", "blocked_confirmed"}:
            exclude = True
        action = "exclude" if exclude else "keep"
        actions[node_key] = action
        assessments[node_key] = _with_policy_action(assessment, action)
        if not exclude:
            kept.append(proxy)
    return kept, actions


def count_statuses(assessments: dict[str, VerificationAssessment]) -> Counter:
    return Counter(assessment.status for assessment in assessments.values())

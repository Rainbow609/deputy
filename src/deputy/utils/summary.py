"""Release notes builder, CI probe JSON, fetch status rows, region stats.

Mirrors mihomo-config's ``utils/summary.py`` for parity but keeps deputy's
existing Chinese release notes format (``build_release_notes``).
"""

from __future__ import annotations

from collections import Counter
import json
import re
import sys
from typing import Any, Iterable

from deputy.probing.tcp import ProbeResult
from deputy.probing.verification import VerificationAssessment
from deputy.sources.subscription import SubscriptionFetchResult
from deputy.utils.logging import is_ci


def build_release_notes(
    *,
    version: str,
    stats: dict,
    failed_sources: list[tuple[str, str]] | None = None,
) -> str:
    """Produce the GitHub Release body (Markdown)."""
    lines: list[str] = [f"# {version}", ""]
    lines.append("## 节点统计")
    lines.append(f"- 总节点数: {stats.get('total', 0)}")
    lines.append(f"- 存活节点数: {stats.get('alive', 0)}")
    lines.append(f"- 存活率: {stats.get('survival_rate', 0):.1f}%")
    lines.append("")
    lines.append("## 延迟统计")
    lines.append(f"- 平均延迟: {stats.get('latency_avg', 0):.1f} ms")
    lines.append(f"- 最低延迟: {stats.get('latency_min', 'N/A')} ms")
    lines.append(f"- 最高延迟: {stats.get('latency_max', 'N/A')} ms")
    lines.append("")
    lines.append("## 变更")
    lines.append(f"- 新增节点: {stats.get('added', 0)}")
    lines.append(f"- 失效节点: {stats.get('removed', 0)}")
    if stats.get("status_counts"):
        lines.append("")
        lines.append("## 判定结果")
        status_counts = stats["status_counts"]
        lines.append(f"- reachable: {status_counts.get('reachable', 0)}")
        lines.append(f"- suspected_gfw_blocked: {status_counts.get('suspected_gfw_blocked', 0)}")
        lines.append(f"- blocked_confirmed: {status_counts.get('blocked_confirmed', 0)}")
        lines.append(f"- protocol_unhealthy: {status_counts.get('protocol_unhealthy', 0)}")
        lines.append(f"- 过滤模式: {stats.get('filter_mode', 'mark')}")
        lines.append(f"- 被过滤节点: {stats.get('filtered_out', 0)}")
    verification_overview = stats.get("verification_overview") or {}
    if verification_overview.get("cn_sample_count", 0) > 0:
        lines.append("")
        lines.append("## 大陆拨测")
        lines.append(f"- Provider: {verification_overview.get('cn_provider', 'unknown')}")
        lines.append(f"- 尝试 Providers: {', '.join(verification_overview.get('cn_attempted_providers', []))}")
        lines.append(f"- 覆盖节点: {verification_overview.get('cn_nodes', 0)}")
        lines.append(f"- 样本总数: {verification_overview.get('cn_sample_count', 0)}")
        lines.append(f"- 成功样本: {verification_overview.get('cn_success_count', 0)}")
        lines.append(f"- 超时样本: {verification_overview.get('cn_timeout_count', 0)}")
        lines.append(f"- 拒绝样本: {verification_overview.get('cn_refused_count', 0)}")
        lines.append(f"- 重置样本: {verification_overview.get('cn_reset_count', 0)}")
        lines.append(f"- 样本成功率: {verification_overview.get('cn_success_rate', 0):.1f}%")
    if failed_sources:
        lines.append("")
        lines.append("## 失败的订阅源")
        for name, reason in failed_sources:
            lines.append(f"- {name}: {reason}")
    return "\n".join(lines) + "\n"


def fetch_status_rows(fetch_results: Iterable[SubscriptionFetchResult]) -> list[tuple]:
    """Build Markdown table rows from subscription fetch results."""
    rows: list[tuple] = []
    for r in fetch_results:
        if r.status == "fresh":
            label = "✅ 已更新" if r.cache_status == "updated" else "✅ 未变化"
            detail = ""
        elif r.status == "fallback":
            label = "🔄 缓存"
            detail = f" (缓存时间: {r.updated_at})" if r.updated_at else ""
        elif r.status == "failed":
            label = "❌ 失败"
            detail = ""
        else:
            label = f"❓ {r.status}"
            detail = ""
        rows.append((r.source, label, str(len(r.proxies)) + detail))
    return rows


def build_probe_json_payload(filtered: list[dict], probe_result: ProbeResult) -> str:
    """Build the CI probe JSON payload, mirroring mihomo-config."""
    alive_with_stats = []
    for p in probe_result.alive:
        entry = {"name": p.get("name", "")}
        stats = probe_result.stats_by_name.get(p.get("name", ""), {})
        if stats:
            entry.update(stats)
        alive_with_stats.append(entry)

    return json.dumps(
        {
            "phase": "tcp_probe",
            "total": len(filtered),
            "alive": len(probe_result.alive),
            "alive_nodes": alive_with_stats,
            "dead": [{"name": p.get("name", ""), "reason": r} for p, r in probe_result.dead],
        },
        ensure_ascii=False,
    )


def build_verification_json_payload(
    assessments: dict[str, VerificationAssessment],
    *,
    filtered_count: int,
) -> str:
    overview = summarize_verification_assessments(assessments)
    return json.dumps(
        {
            "phase": "verification",
            "total": filtered_count,
            "overview": overview,
            "nodes": [assessment.to_dict() for assessment in assessments.values()],
        },
        ensure_ascii=False,
    )


def summarize_verification_assessments(
    assessments: dict[str, VerificationAssessment | dict[str, Any]],
) -> dict[str, Any]:
    provider_counts: Counter[str] = Counter()
    attempted_provider_counts: Counter[str] = Counter()
    cn_nodes = 0
    cn_sample_count = 0
    cn_success_count = 0
    cn_timeout_count = 0
    cn_reset_count = 0
    cn_refused_count = 0

    for raw in assessments.values():
        signal_summary = raw.signal_summary if isinstance(raw, VerificationAssessment) else raw.get("signal_summary", {})
        cn_tcp = signal_summary.get("cn_tcp", {}) if isinstance(signal_summary, dict) else {}
        sample_count = int(cn_tcp.get("sample_count", 0) or 0)
        success_count = int(cn_tcp.get("success_count", 0) or 0)
        timeout_count = int(cn_tcp.get("timeout_count", 0) or 0)
        reset_count = int(cn_tcp.get("reset_count", 0) or 0)
        refused_count = int(cn_tcp.get("refused_count", 0) or 0)
        source_provider = str(cn_tcp.get("source_provider", "") or "")
        attempted_providers = [str(item) for item in (cn_tcp.get("attempted_providers", []) or []) if item]
        samples = cn_tcp.get("samples", []) or []

        if sample_count > 0:
            cn_nodes += 1
        cn_sample_count += sample_count
        cn_success_count += success_count
        cn_timeout_count += timeout_count
        cn_reset_count += reset_count
        cn_refused_count += refused_count

        sample_provider = ""
        if not source_provider:
            for sample in samples:
                if isinstance(sample, dict) and sample.get("provider"):
                    sample_provider = str(sample["provider"])
                    break

        if source_provider:
            provider_counts[source_provider] += 1
        elif sample_provider:
            provider_counts[sample_provider] += 1
        for provider in attempted_providers:
            attempted_provider_counts[provider] += 1

    cn_success_rate = round((cn_success_count / cn_sample_count) * 100, 1) if cn_sample_count else 0.0
    return {
        "cn_provider": provider_counts.most_common(1)[0][0] if provider_counts else "",
        "cn_attempted_providers": [name for name, _ in attempted_provider_counts.most_common()],
        "cn_nodes": cn_nodes,
        "cn_sample_count": cn_sample_count,
        "cn_success_count": cn_success_count,
        "cn_timeout_count": cn_timeout_count,
        "cn_reset_count": cn_reset_count,
        "cn_refused_count": cn_refused_count,
        "cn_success_rate": cn_success_rate,
    }


def print_ci_probe_json(filtered: list[dict], probe_result: ProbeResult) -> None:
    """Print CI probe JSON when running in GitHub Actions."""
    if is_ci():
        print(
            f"[PROBE_JSON]{build_probe_json_payload(filtered, probe_result)}[/PROBE_JSON]",
            file=sys.stderr,
        )


def print_ci_verification_json(assessments: dict[str, VerificationAssessment], *, filtered_count: int) -> None:
    if is_ci():
        print(
            f"[VERIFICATION_JSON]{build_verification_json_payload(assessments, filtered_count=filtered_count)}[/VERIFICATION_JSON]",
            file=sys.stderr,
        )


def region_counts(alive_names: list[str]) -> dict[str, int]:
    """Bucket alive nodes by region using simple regex heuristics."""
    patterns = {
        "hk": r"(?i)香港|HK|Hong",
        "jp": r"(?i)日本|JP|Japan",
        "us": r"(?i)美国|US|United States",
        "sg": r"(?i)新加坡|SG|Singapore",
        "tw": r"(?i)台湾|TW|Taiwan",
    }
    counts = {k: 0 for k in patterns}
    for name in alive_names:
        for k, pat in patterns.items():
            if re.search(pat, name):
                counts[k] += 1
                break
    return counts


def print_latency_overview(stats_by_name: dict[str, dict]) -> None:
    """Print aggregate latency stats to the console."""
    if not stats_by_name:
        return
    all_latencies = [s["avg_ms"] for s in stats_by_name.values() if "avg_ms" in s]
    if all_latencies:
        overall_avg = round(sum(all_latencies) / len(all_latencies), 1)
        overall_min = min(all_latencies)
        overall_max = max(all_latencies)
        print(
            f"  延迟统计: avg={overall_avg}ms min={overall_min}ms "
            f"max={overall_max}ms nodes={len(all_latencies)}"
        )

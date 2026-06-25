"""Release notes builder, CI probe JSON, fetch status rows, region stats.

Mirrors mihomo-config's ``utils/summary.py`` for parity but keeps deputy's
existing Chinese release notes format (``build_release_notes``).
"""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable

from deputy.probing.tcp import ProbeResult
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


def print_ci_probe_json(filtered: list[dict], probe_result: ProbeResult) -> None:
    """Print CI probe JSON when running in GitHub Actions."""
    if is_ci():
        print(
            f"[PROBE_JSON]{build_probe_json_payload(filtered, probe_result)}[/PROBE_JSON]",
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

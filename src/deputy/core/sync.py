"""End-to-end orchestration entry point for deputy.

Pipeline:
1. Load ``sync_config.toml`` (DeputyConfig dataclass).
2. For each subscription source, fetch via ``TransportChain`` with retry /
   backoff, falling back to the last successful cache on temporary errors.
3. Sanitize node names and apply per-source rename rules.
4. Verify each node via TCP probing (``tcp_probe``).
5. Compute quality metrics (survival rate, latency stats).
6. Render ``config.yaml`` from ``config.template.yaml``.
7. Publish to GitHub Releases via the conditional ``ReleasePublisher`` (the
   actual ``softprops/action-gh-release@v2`` step runs in ``.github/workflows/
   sync-and-release.yml``; locally, ``ReleasePublisher.default`` is a no-op).

This module replaces the legacy 251-line ``scripts/sync_nodes.py``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

from deputy.core.nodes import (
    apply_node_rename,
    build_rename_config,
    deduplicate_proxies,
    group_by_source,
)
from deputy.probing.cn import get_china_probe_provider
from deputy.probing.health import MihomoDelayChecker
from deputy.probing.tcp import tcp_probe
from deputy.probing.verification import (
    apply_policy,
    assess_nodes,
    count_statuses,
    load_history,
    save_history,
)
from deputy.publishing.release import ReleasePublisher, make_version_tag
from deputy.rendering.config import render_template
from deputy.sources.config import DeputyConfig, load_config
from deputy.sources.subscription import (
    SubscriptionFetchResult,
    default_transports,
    fetch_subscription_with_cache,
    prune_subscription_caches,
)
from deputy.transport.chain import TransportChain
from deputy.utils.logging import GhaLogger, LogLevel, StepSummaryBuilder, group as gha_group, endgroup as gha_endgroup
from deputy.utils.quality import compute_latency_stats, compute_survival_rate
from deputy.utils.summary import (
    build_release_notes,
    fetch_status_rows,
    print_ci_probe_json,
    print_ci_verification_json,
    print_latency_overview,
    region_counts,
    summarize_verification_assessments,
)


DEFAULT_OUTPUT_CONFIG = Path("config.yaml")
DEFAULT_PREVIOUS_CONFIG = Path("config.previous.yaml")
DEFAULT_CACHE_DIR = Path("subscriptions")


# ── Pure helpers ────────────────────────────────────────────────────────────


def parse_clash_yaml(text: str) -> dict[str, Any]:
    return yaml.safe_load(text) or {}


def load_previous_config(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_transport_chain(fetch_cfg=None) -> TransportChain:
    """Build the default transport chain with backoff parameters from config."""
    cfg = fetch_cfg or {}
    return TransportChain(
        default_transports(),
        max_attempts_per_transport=cfg.get("max_attempts_per_transport", 4),
        max_total_attempts=cfg.get("max_total_attempts", 20),
        base_delay=cfg.get("base_delay", 0.5),
        max_delay=cfg.get("max_delay", 8.0),
        jitter_range=cfg.get("jitter_range", 0.3),
    )


def _resolve_history_path(config_path: Path, configured_path: str) -> Path | None:
    if not configured_path:
        return None
    path = Path(configured_path)
    if not path.is_absolute():
        path = config_path.parent / path
    return path


# ── Main pipeline ───────────────────────────────────────────────────────────


def run_sync(
    *,
    config_path: Path,
    template_path: Path,
    output_config: Path = DEFAULT_OUTPUT_CONFIG,
    previous_config: Path = DEFAULT_PREVIOUS_CONFIG,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    logger: GhaLogger | None = None,
) -> dict:
    """End-to-end sync. Returns a summary dict.

    Mirrors the legacy ``scripts.sync_nodes.run_sync`` contract so existing
    tests / callers keep working, but adds:

    - subscription cache fallback via ``fetch_subscription_with_cache``
    - 6-transport chain (vs the legacy 3)
    - GitHub Actions Step Summary via ``StepSummaryBuilder``
    """
    logger = logger or GhaLogger("deputy")
    logger.set_level(LogLevel.INFO)
    config: DeputyConfig = load_config(config_path)

    # Prune caches for sources that are no longer configured.
    prune_subscription_caches(cache_dir, config.subscription_sources.keys())

    chain = build_transport_chain(
        {
            "max_attempts_per_transport": config.fetch.max_attempts_per_transport,
            "max_total_attempts": config.fetch.max_total_attempts,
            "base_delay": config.fetch.base_delay,
            "max_delay": config.fetch.max_delay,
            "jitter_range": config.fetch.jitter_range,
        }
    )

    logger.info(
        "loading config",
        {
            "sources": len(config.subscription_sources),
            "static_nodes": len(config.static_nodes),
        },
    )

    # 1. Fetch all subscriptions in parallel.
    fetch_results: list[SubscriptionFetchResult] = []
    failed_sources: list[tuple[str, str]] = []
    with logger.group("fetch subscriptions"):
        with ThreadPoolExecutor(
            max_workers=min(8, len(config.subscription_sources) or 1)
        ) as ex:
            futures = {
                ex.submit(
                    fetch_subscription_with_cache,
                    url,
                    name,
                    cache_dir=cache_dir,
                    fetch_cfg=config.fetch,
                    transport_chain=chain,
                ): name
                for name, url in config.subscription_sources.items()
            }
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    failed_sources.append((name, str(e)))
                    logger.warning(
                        "source failed", {"source": name, "error": str(e)}
                    )
                    continue
                fetch_results.append(result)
                logger.info(
                    "fetched",
                    {
                        "source": name,
                        "count": len(result.proxies),
                        "status": result.status,
                    },
                )

    # 2. Apply per-source rename + sanitize.
    rename_raw = config.rename
    global_rename = {k: v for k, v in rename_raw.items() if not isinstance(v, dict)}
    by_source = group_by_source(
        (r.source, p)
        for r in fetch_results
        for p in r.proxies
        if p.get("name")
        and not any(
            kw in (p.get("name", "") or "")
            for kw in config.subscription.exclude_keywords
        )
    )
    filtered: list[dict[str, Any]] = []
    for source_name, source_proxies in by_source.items():
        source_rename = (
            rename_raw.get(source_name)
            if isinstance(rename_raw.get(source_name), dict)
            else None
        )
        rename_cfg = build_rename_config(global_rename or None, source_rename)
        filtered.extend(apply_node_rename(source_proxies, source_name, rename_cfg))

    # 3. Combine with static nodes and deduplicate by (server, port).
    static = config.static_nodes
    combined = static + filtered
    deduped = deduplicate_proxies(combined)

    # 4. TCP probe.
    with logger.group("verify nodes"):
        probe_result = tcp_probe(
            deduped,
            timeout=config.probe.timeout,
            concurrency=config.probe.concurrency,
            retries=config.probe.retries,
            address_family=config.probe.address_family,
        )
    alive_nodes = probe_result.alive
    dead_nodes = probe_result.dead
    if not alive_nodes:
        raise RuntimeError(
            "node verification produced zero alive nodes; refusing to publish empty config"
        )

    history_path = _resolve_history_path(config_path, config.probe.classifier.history_path)
    history = load_history(history_path) if history_path else {}
    assessments = assess_nodes(
        deduped,
        probe_result,
        cn_config=config.probe.cn,
        health_config=config.probe.health,
        classifier=config.probe.classifier,
        history=history,
        cn_provider=get_china_probe_provider(config.probe.cn.provider),
        health_checker=MihomoDelayChecker(),
    )
    policy_alive_nodes, policy_actions = apply_policy(
        alive_nodes,
        assessments,
        config.probe.classifier.filter_mode,
    )
    if history_path:
        save_history(
            history_path,
            {key: assessment.history for key, assessment in assessments.items()},
        )
    status_counts = count_statuses(assessments)
    verification_overview = summarize_verification_assessments(assessments)
    policy_counts = Counter(policy_actions.values())
    filtered_out = policy_counts.get("exclude", 0)
    if not policy_alive_nodes:
        raise RuntimeError(
            "node verification produced zero publishable nodes after policy filtering"
        )
    logger.info(
        "verification done",
        {
            "alive": len(policy_alive_nodes),
            "dead": len(dead_nodes),
            "total": len(deduped),
            "filtered_out": filtered_out,
        },
    )
    print_latency_overview(probe_result.stats_by_name)

    survival_rate = compute_survival_rate(alive=len(policy_alive_nodes), total=len(deduped))
    latencies = [
        info.get("avg_ms")  # type: ignore[union-attr]
        for proxy, info in zip(policy_alive_nodes, [probe_result.stats_by_name.get(p.get("name", ""), {}) for p in policy_alive_nodes])
        if info and info.get("avg_ms") is not None
    ]
    # Fallback to per-result latency_ms (latency_stats works with floats).
    if not latencies:
        # Build latencies list from stats dict by name.
        for p in policy_alive_nodes:
            info = probe_result.stats_by_name.get(p.get("name", ""), {})
            if "avg_ms" in info:
                latencies.append(info["avg_ms"])
    latency_stats = compute_latency_stats(latencies)

    # 5. Render template.
    with logger.group("render template"):
        output_text = render_template(
            template_path,
            local_proxies=static,
            sub_proxies=policy_alive_nodes,
        )
    output_config.write_text(output_text, encoding="utf-8")

    previous_text = load_previous_config(previous_config)
    version_tag = make_version_tag()
    notes = build_release_notes(
        version=version_tag,
        stats={
            "total": len(deduped),
            "alive": len(policy_alive_nodes),
            "survival_rate": survival_rate,
            "latency_avg": latency_stats["avg"],
            "latency_min": latency_stats["min"],
            "latency_max": latency_stats["max"],
            "added": 0,
            "removed": len(dead_nodes),
            "status_counts": dict(status_counts),
            "filter_mode": config.probe.classifier.filter_mode,
            "filtered_out": filtered_out,
            "verification_overview": verification_overview,
        },
        failed_sources=failed_sources,
    )

    # 6. Publish to GitHub Releases (no-op locally; the GHA workflow runs the
    # actual softprops/action-gh-release@v2 step on config.yaml afterwards).
    publisher = ReleasePublisher.default(
        output_dir=output_config.parent, config_path=output_config
    )
    publish_result = publisher.publish(
        version_tag=version_tag,
        release_notes=notes,
        previous_config_text=previous_text,
    )

    # 7. GitHub Actions Step Summary (no-op outside CI).
    try:
        sb = StepSummaryBuilder()
        sb.heading("Deputy 同步结果", level=2)
        sb.table(
            ["指标", "数量"],
            [
                ("订阅源", str(len(config.subscription_sources))),
                ("静态节点", str(len(static))),
                ("订阅节点", str(len(filtered))),
                ("存活节点", str(len(policy_alive_nodes))),
                ("失效节点", str(len(dead_nodes))),
                ("存活率", f"{survival_rate:.1f}%"),
                ("过滤模式", config.probe.classifier.filter_mode),
                ("被过滤节点", str(filtered_out)),
            ],
        )
        sb.heading("判定结果", level=3)
        sb.table(
            ["状态", "数量"],
            [
                ("reachable", str(status_counts.get("reachable", 0))),
                ("suspected_gfw_blocked", str(status_counts.get("suspected_gfw_blocked", 0))),
                ("blocked_confirmed", str(status_counts.get("blocked_confirmed", 0))),
                ("protocol_unhealthy", str(status_counts.get("protocol_unhealthy", 0))),
            ],
        )
        if verification_overview.get("cn_sample_count", 0) > 0:
            sb.heading("大陆拨测摘要", level=3)
            sb.table(
                ["指标", "数值"],
                [
                    ("Provider", verification_overview.get("cn_provider", "")),
                    ("尝试 Providers", ", ".join(verification_overview.get("cn_attempted_providers", []))),
                    ("覆盖节点", str(verification_overview.get("cn_nodes", 0))),
                    ("样本总数", str(verification_overview.get("cn_sample_count", 0))),
                    ("成功样本", str(verification_overview.get("cn_success_count", 0))),
                    ("超时样本", str(verification_overview.get("cn_timeout_count", 0))),
                    ("拒绝样本", str(verification_overview.get("cn_refused_count", 0))),
                    ("重置样本", str(verification_overview.get("cn_reset_count", 0))),
                    ("样本成功率", f"{verification_overview.get('cn_success_rate', 0):.1f}%"),
                ],
            )
        if failed_sources:
            sb.heading("失败的订阅源", level=3)
            sb.table(["订阅源", "原因"], failed_sources)
        sb.heading("订阅源状态", level=3)
        sb.table(["订阅源", "状态", "节点数"], fetch_status_rows(fetch_results))
        if policy_alive_nodes:
            region = region_counts([p.get("name", "") for p in policy_alive_nodes])
            sb.heading("地区分布", level=3)
            sb.table(
                ["地区", "节点数"],
                [
                    ("🇭🇰 香港", str(region["hk"])),
                    ("🇯🇵 日本", str(region["jp"])),
                    ("🇺🇸 美国", str(region["us"])),
                    ("🇸🇬 新加坡", str(region["sg"])),
                    ("🇹🇼 台湾", str(region["tw"])),
                ],
            )
        sb.write()
    except Exception:
        # Step summary is best-effort; never fail the run over it.
        pass

    # CI-only: emit [PROBE_JSON] markers for downstream tooling.
    print_ci_probe_json(deduped, probe_result)
    print_ci_verification_json(assessments, filtered_count=len(deduped))

    return {
        "version": version_tag,
        "publish": publish_result,
        "survival_rate": survival_rate,
        "alive": len(policy_alive_nodes),
        "dead": len(dead_nodes),
        "failed_sources": failed_sources,
        "fetch_results": [r.__dict__ for r in fetch_results],
        "status_counts": status_counts,
        "policy_counts": policy_counts,
        "filtered_out": filtered_out,
        "verification_overview": verification_overview,
        "assessments": {key: value.to_dict() for key, value in assessments.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync deputy node configuration")
    parser.add_argument("--config", type=Path, default=Path("sync_config.toml"))
    parser.add_argument("--template", type=Path, default=Path("config.template.yaml"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CONFIG)
    parser.add_argument("--previous", type=Path, default=DEFAULT_PREVIOUS_CONFIG)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args()

    gha_group("📥 deputy sync")
    try:
        summary = run_sync(
            config_path=args.config,
            template_path=args.template,
            output_config=args.output,
            previous_config=args.previous,
            cache_dir=args.cache_dir,
        )
    finally:
        gha_endgroup()

    print(
        f"sync done: version={summary['version']} survival={summary['survival_rate']:.1f}%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

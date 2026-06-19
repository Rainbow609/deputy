"""Main orchestration script for deputy.

Pipeline:
1. Load nodes.toml (TOML config)
2. For each subscription source, fetch via TransportChain
3. Parse Clash YAML and filter by exclude_keywords
4. Verify each proxy (TCP probe)
5. Compute quality metrics
6. Render config.yaml from template
7. Publish to GitHub Releases (conditional on change)

This is a direct port of mihomo-config's sync_nodes.py orchestration,
simplified to a single platform output.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

from scripts.fetch_transport import (
    CloudscraperTransport,
    CurlCffiTransport,
    RequestsTransport,
    TransportChain,
    TransportError,
)
from scripts.github_actions_logger import GhaLogger, LogLevel
from scripts.node_verifier import NodeVerifier
from scripts.quality_metrics import (
    compute_latency_stats,
    compute_survival_rate,
    format_release_notes,
)
from scripts.release_publisher import ReleasePublisher, make_version_tag
from scripts.template_renderer import render_template
from scripts.toml_config import load_config


DEFAULT_OUTPUT_CONFIG = Path("config.yaml")
DEFAULT_PREVIOUS_CONFIG = Path("config.previous.yaml")


def parse_clash_yaml(text: str) -> dict[str, Any]:
    return yaml.safe_load(text) or {}


def filter_proxies(
    proxies: list[dict[str, Any]], *, exclude_keywords: list[str]
) -> list[dict[str, Any]]:
    if not exclude_keywords:
        return proxies
    out: list[dict[str, Any]] = []
    for p in proxies:
        name = p.get("name", "") or ""
        if any(kw in name for kw in exclude_keywords):
            continue
        out.append(p)
    return out


def deduplicate_proxies(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set = set()
    out: list[dict[str, Any]] = []
    for p in proxies:
        key = (p.get("server"), p.get("port"))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def fetch_subscription_yaml(
    chain: TransportChain, source_name: str, url: str
) -> list[dict[str, Any]]:
    """Fetch a subscription URL and return its proxy list."""
    try:
        result = chain.fetch(url, timeout=15)
    except TransportError as e:
        detail = f" (status={e.status_code})" if e.status_code is not None else ""
        raise RuntimeError(f"failed to fetch {source_name}: {e}{detail}") from e
    data = parse_clash_yaml(result.text())
    return list(data.get("proxies") or [])


def load_previous_config(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_transport_chain() -> TransportChain:
    """Build the standard mihomo-config transport chain."""
    transports = [CloudscraperTransport(), RequestsTransport(), CurlCffiTransport()]
    return TransportChain(transports, max_attempts=4)


def run_sync(
    *,
    config_path: Path,
    template_path: Path,
    output_config: Path = DEFAULT_OUTPUT_CONFIG,
    previous_config: Path = DEFAULT_PREVIOUS_CONFIG,
    logger: GhaLogger | None = None,
) -> dict:
    """End-to-end sync. Returns a summary dict."""
    logger = logger or GhaLogger("deputy")
    logger.set_level(LogLevel.INFO)
    config = load_config(config_path)
    chain = build_transport_chain()
    verifier = NodeVerifier(
        timeout=config.probe.timeout,
        retries=config.probe.retries,
        address_family=config.probe.address_family,
    )

    logger.info("loading config", {"sources": len(config.subscription_sources)})
    with logger.group("fetch subscriptions"):
        all_subs: list[tuple[str, dict]] = []
        failed_sources: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(config.subscription_sources) or 1)) as ex:
            futures = {
                ex.submit(fetch_subscription_yaml, chain, name, url): name
                for name, url in config.subscription_sources.items()
            }
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    proxies = fut.result()
                    all_subs.extend((name, p) for p in proxies)
                    logger.info("fetched", {"source": name, "count": len(proxies)})
                except Exception as e:
                    failed_sources.append((name, str(e)))
                    logger.warning("source failed", {"source": name, "error": str(e)})

    all_sub_proxies = [p for _, p in all_subs]
    filtered = filter_proxies(all_sub_proxies, exclude_keywords=config.subscription.exclude_keywords)
    static = config.static_nodes
    if config.subscription_sources and not filtered and not static and failed_sources:
        failed = ", ".join(name for name, _ in failed_sources)
        raise RuntimeError(f"all subscription sources failed; refusing to publish empty config: {failed}")
    combined = static + filtered
    deduped = deduplicate_proxies(combined)

    with logger.group("verify nodes"):
        results = verifier.verify_many(deduped, concurrency=config.probe.concurrency)
    alive_nodes = [n for n, r in results if r.alive]
    dead_nodes = [(n, r) for n, r in results if not r.alive]
    if not alive_nodes:
        raise RuntimeError("node verification produced zero alive nodes; refusing to publish empty config")
    logger.info("verification done", {
        "alive": len(alive_nodes),
        "dead": len(dead_nodes),
        "total": len(deduped),
    })

    survival_rate = compute_survival_rate(alive=len(alive_nodes), total=len(deduped))
    latencies = [r.latency_ms for _, r in results if r.alive and r.latency_ms is not None]
    latency_stats = compute_latency_stats(latencies)

    with logger.group("render template"):
        output_text = render_template(
            template_path,
            local_proxies=static,
            sub_proxies=alive_nodes,
        )
    output_config.write_text(output_text, encoding="utf-8")

    previous_text = load_previous_config(previous_config)
    version_tag = make_version_tag()
    notes = format_release_notes(
        version=version_tag,
        stats={
            "total": len(deduped),
            "alive": len(alive_nodes),
            "survival_rate": survival_rate,
            "latency_avg": latency_stats["avg"],
            "latency_min": latency_stats["min"],
            "latency_max": latency_stats["max"],
            "added": 0,
            "removed": len(dead_nodes),
        },
        failed_sources=failed_sources,
    )

    publisher = ReleasePublisher.default(output_dir=output_config.parent, config_path=output_config)
    publish_result = publisher.publish(
        version_tag=version_tag,
        release_notes=notes,
        previous_config_text=previous_text,
    )

    return {
        "version": version_tag,
        "publish": publish_result,
        "survival_rate": survival_rate,
        "alive": len(alive_nodes),
        "dead": len(dead_nodes),
        "failed_sources": failed_sources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync deputy node configuration")
    parser.add_argument("--config", type=Path, default=Path("nodes.toml"))
    parser.add_argument("--template", type=Path, default=Path("config.template.yaml"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_CONFIG)
    parser.add_argument("--previous", type=Path, default=DEFAULT_PREVIOUS_CONFIG)
    args = parser.parse_args()
    summary = run_sync(
        config_path=args.config,
        template_path=args.template,
        output_config=args.output,
        previous_config=args.previous,
    )
    print(f"sync done: version={summary['version']} survival={summary['survival_rate']:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""TOML configuration loader and atomic file-writer for deputy.

Loads and validates ``sync_config.toml`` (formerly ``nodes.toml``):

- ``[subscription]`` — format and exclude_keywords
- ``[subscription.fetch]`` — exponential-backoff parameters for the
  transport chain (mirrors mihomo-config's fetch block)
- ``[probe]`` — TCP probe tuning (timeout, concurrency, retries, family)
- ``[subscription_sources]`` — static name → URL mapping
- ``[[static_nodes]]`` — hand-curated proxy entries (list of tables)
- ``[rename]`` — global defaults + per-source overrides
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deputy.probing.verification import (
    ChinaProbeConfig,
    ProbeHealthConfig,
    VerificationClassifierConfig,
    VALID_FILTER_MODES,
)


class ConfigError(Exception):
    """Raised when TOML config is invalid or missing."""


@dataclass
class SubscriptionConfig:
    format: str = "clash"
    exclude_keywords: list[str] = field(default_factory=list)


@dataclass
class FetchConfig:
    """Transport-chain retry/backoff tuning. Values mirror mihomo-config."""

    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter_range: float = 0.3
    max_attempts_per_transport: int = 4
    max_total_attempts: int = 20
    timeout: int = 45


@dataclass
class ProbeConfig:
    timeout: int = 3
    concurrency: int = 30
    retries: int = 0
    address_family: str = "auto"
    cn: ChinaProbeConfig = field(default_factory=ChinaProbeConfig)
    health: ProbeHealthConfig = field(default_factory=ProbeHealthConfig)
    classifier: VerificationClassifierConfig = field(default_factory=VerificationClassifierConfig)


@dataclass
class DeputyConfig:
    subscription: SubscriptionConfig
    probe: ProbeConfig
    fetch: FetchConfig
    static_nodes: list[dict[str, Any]] = field(default_factory=list)
    subscription_sources: dict[str, str] = field(default_factory=dict)
    rename: dict[str, Any] = field(default_factory=dict)


def _build_subscription(raw: dict[str, Any]) -> SubscriptionConfig:
    fmt = raw.get("format", "clash")
    if fmt not in {"clash", "v2ray"}:
        raise ConfigError(f"不支持的订阅格式: {fmt}")
    return SubscriptionConfig(
        format=fmt,
        exclude_keywords=list(raw.get("exclude_keywords", [])),
    )


def _build_fetch(raw: dict[str, Any] | None) -> FetchConfig:
    raw = raw or {}
    return FetchConfig(
        base_delay=float(raw.get("base_delay", 0.5)),
        max_delay=float(raw.get("max_delay", 8.0)),
        jitter_range=float(raw.get("jitter_range", 0.3)),
        max_attempts_per_transport=int(raw.get("max_attempts_per_transport", 4)),
        max_total_attempts=int(raw.get("max_total_attempts", 20)),
        timeout=int(raw.get("timeout", 45)),
    )


def _build_probe(raw: dict[str, Any]) -> ProbeConfig:
    concurrency = int(raw.get("concurrency", 30))
    if concurrency < 1 or concurrency > 200:
        raise ConfigError(f"concurrency 必须在 1-200 之间, 当前: {concurrency}")
    timeout = int(raw.get("timeout", 3))
    if timeout < 1 or timeout > 30:
        raise ConfigError(f"timeout 必须在 1-30 秒之间, 当前: {timeout}")
    cn_raw = raw.get("cn", {}) if isinstance(raw.get("cn", {}), dict) else {}
    health_raw = raw.get("health", {}) if isinstance(raw.get("health", {}), dict) else {}
    classifier_raw = raw.get("classifier", {}) if isinstance(raw.get("classifier", {}), dict) else {}
    filter_mode = str(classifier_raw.get("filter_mode", "mark"))
    if filter_mode not in VALID_FILTER_MODES:
        raise ConfigError(f"filter_mode 必须是 {sorted(VALID_FILTER_MODES)}, 当前: {filter_mode}")

    return ProbeConfig(
        timeout=timeout,
        concurrency=concurrency,
        retries=int(raw.get("retries", 0)),
        address_family=str(raw.get("address_family", "auto")),
        cn=ChinaProbeConfig(
            enabled=bool(cn_raw.get("enabled", False)),
            provider=str(cn_raw.get("provider", "noop")),
            min_vantages=int(cn_raw.get("min_vantages", 3)),
            min_success_vantages=int(cn_raw.get("min_success_vantages", 2)),
            timeout=int(cn_raw.get("timeout", 5)),
            stale_after_seconds=int(cn_raw.get("stale_after_seconds", 600)),
        ),
        health=ProbeHealthConfig(
            enabled=bool(health_raw.get("enabled", False)),
            kind=str(health_raw.get("kind", "mihomo_delay")),
            controller_url=str(health_raw.get("controller_url", "http://127.0.0.1:9093")),
            secret=str(health_raw.get("secret", "")),
            test_url=str(health_raw.get("test_url", "https://www.gstatic.com/generate_204")),
            timeout_ms=int(health_raw.get("timeout_ms", 10_000)),
            expected=str(health_raw.get("expected", "200,204")),
        ),
        classifier=VerificationClassifierConfig(
            confirm_after_runs=int(classifier_raw.get("confirm_after_runs", 3)),
            filter_mode=filter_mode,
            history_path=str(classifier_raw.get("history_path", "")),
        ),
    )


def _validate_rename_table(raw: dict[str, Any], *, path: str = "rename") -> dict[str, Any]:
    validated: dict[str, Any] = {}
    for key, value in raw.items():
        if key in {"sanitize", "separator", "prefix"}:
            if key == "sanitize":
                if not isinstance(value, bool):
                    raise ConfigError(f"{path}.sanitize 必须是 bool")
            elif not isinstance(value, str):
                raise ConfigError(f"{path}.{key} 必须是 string")
            validated[key] = value
            continue

        if not isinstance(value, dict):
            raise ConfigError(f"{path}.{key} 必须是 table")
        validated[key] = _validate_rename_table(value, path=f"{path}.{key}")

    return validated


def load_config(path: Path) -> DeputyConfig:
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"TOML 解析失败: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("TOML 根节点必须是 table")

    sub = _build_subscription(raw.get("subscription", {}))
    sub_raw = raw.get("subscription", {})
    fetch = _build_fetch(sub_raw.get("fetch") if isinstance(sub_raw, dict) else None)
    probe = _build_probe(raw.get("probe", {}))
    static = list(raw.get("static_nodes", []))
    sources = dict(raw.get("subscription_sources", {}))
    rename_raw = raw.get("rename", {})
    if not isinstance(rename_raw, dict):
        raise ConfigError("rename 必须是 table")
    rename = _validate_rename_table(rename_raw)

    return DeputyConfig(
        subscription=sub,
        probe=probe,
        fetch=fetch,
        static_nodes=static,
        subscription_sources=sources,
        rename=rename,
    )


def write_text_atomic(path: Path, text: str) -> None:
    """Write text to path via a temporary file and atomic replace.

    Prevents partial writes from corrupting the released ``config.yaml``
    asset when interrupted mid-flush.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise

"""TOML configuration parser for deputy.

Loads and validates nodes.toml containing:
- subscription settings (format, exclude_keywords)
- probe settings (timeout, concurrency, retries, address_family)
- static_nodes list
- subscription_sources dict
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when TOML config is invalid or missing."""


@dataclass
class SubscriptionConfig:
    format: str = "clash"
    exclude_keywords: list[str] = field(default_factory=list)


@dataclass
class ProbeConfig:
    timeout: int = 3
    concurrency: int = 30
    retries: int = 0
    address_family: str = "auto"


@dataclass
class DeputyConfig:
    subscription: SubscriptionConfig
    probe: ProbeConfig
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


def _build_probe(raw: dict[str, Any]) -> ProbeConfig:
    concurrency = int(raw.get("concurrency", 30))
    if concurrency < 1 or concurrency > 200:
        raise ConfigError(f"concurrency 必须在 1-200 之间, 当前: {concurrency}")
    timeout = int(raw.get("timeout", 3))
    if timeout < 1 or timeout > 30:
        raise ConfigError(f"timeout 必须在 1-30 秒之间, 当前: {timeout}")
    return ProbeConfig(
        timeout=timeout,
        concurrency=concurrency,
        retries=int(raw.get("retries", 0)),
        address_family=str(raw.get("address_family", "auto")),
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
        static_nodes=static,
        subscription_sources=sources,
        rename=rename,
    )

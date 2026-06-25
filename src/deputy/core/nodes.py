"""Pure node filtering, sanitization, deduplication, and merge rules.

Combines deputy's legacy ``node_renamer.py`` and ``sync_nodes.py`` helpers
with mihomo-config's ``core/nodes.py`` style.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Any


# ── Module-level constants ──────────────────────────────────────────────────

_SANITIZE_ASCII_PUNCT = re.compile(r"[|()\[\]{}<>!@#$%^&*=+`~?]")
_SANITIZE_SYMBOL_CAT = ("So", "Sm")
_FULLWIDTH_SPACE = "　"

_BENCHMARK_RANGE_PREFIX = (198, (18, 19))

# Protocol prefixes that appear in node names (e.g. "VMESS-美国").
_PROTOCOL_PREFIXES = re.compile(
    r"^(?:VMESS|VMess|vmess|SS|ss|SSR|ssr|Trojan|trojan|VLESS|vless|Hysteria|hysteria)\s*-\s*"
)

# Unlock / feature suffixes like "-NF解锁...", "-ChatGPT", "-TikTok", "-YouTube".
# We strip everything from the first such marker onward.
_UNLOCK_MARKERS = re.compile(
    r"-NF(?:解锁|解鎖)[^\s-]*(?:\s*-\s*[^\s-]+)*|"
    r"-ChatGPT|"
    r"-TikTok|"
    r"-YouTube|"
    r"-Netflix|"
    r"-Disney\+|"
    r"-HBO|"
    r"-Spotify|"
    r"-解锁[^\s-]*|"
    r"-解鎖[^\s-]*"
)

# Server address at the end (IP:port or domain:port).
_SERVER_SUFFIX = re.compile(r"-[a-zA-Z0-9][a-zA-Z0-9._-]*:\d{2,5}$")


# ── sanitize_node_name ──────────────────────────────────────────────────────


def _strip_protocol(name: str) -> str:
    """Remove protocol prefix like VMESS-, SS-, SSR-, Trojan- etc."""
    return _PROTOCOL_PREFIXES.sub("", name)


def _strip_unlock_markers(name: str) -> str:
    """Remove unlock/feature suffixes and everything after them."""
    match = _UNLOCK_MARKERS.search(name)
    if match:
        return name[:match.start()]
    return name


def _strip_server_suffix(name: str) -> str:
    """Remove trailing server address like -1.2.3.4:8080 or -domain.com:443."""
    return _SERVER_SUFFIX.sub("", name)


def sanitize_node_name(name: str) -> str:
    """Normalize subscription node names before prefixing them.

    Steps (order matters; each handles characters not covered by earlier steps):
    1. Strip protocol prefix (VMESS-, SS-, SSR-, Trojan- etc.).
    2. Strip unlock/feature suffixes (NF解锁..., ChatGPT, TikTok, YouTube etc.).
    3. Strip trailing server address (IP:port or domain:port).
    4. Strip ASCII punctuation: ``|()[]{}!@#$%^&*=+`~?``
    5. Strip emoji / decorative symbols: Unicode category ``So`` / ``Sm``.
    6. Fullwidth space U+3000 → halfwidth space.
    7. Collapse runs of whitespace to a single halfwidth space.
    8. Strip leading / trailing whitespace.

    Returns ``""`` when the result is empty; callers are responsible for
    dropping such nodes.
    """
    if not name:
        return ""

    s = _strip_protocol(name)
    s = _strip_unlock_markers(s)
    s = _strip_server_suffix(s)
    s = _SANITIZE_ASCII_PUNCT.sub("", s)
    s = "".join(c for c in s if unicodedata.category(c) not in _SANITIZE_SYMBOL_CAT)
    s = s.replace(_FULLWIDTH_SPACE, " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ── RenameConfig + apply_node_rename ────────────────────────────────────────


@dataclass
class RenameConfig:
    """Per-source rename settings."""

    prefix: str = ""
    sanitize: bool = True
    separator: str = "-"
    max_length: int = 0  # 0 means no limit


@dataclass(frozen=True)
class MergeResult:
    local_proxies: list[dict] = field(default_factory=list)
    sub_proxies: list[dict] = field(default_factory=list)
    dialer_names: list[str] = field(default_factory=list)


def build_rename_config(
    global_rename: dict[str, Any] | None,
    source_rename: dict[str, Any] | None,
) -> RenameConfig:
    """Merge global defaults with per-source overrides (source wins)."""
    merged: dict[str, Any] = {}
    if global_rename:
        merged.update(global_rename)
    if source_rename:
        merged.update(source_rename)

    return RenameConfig(
        prefix=str(merged.get("prefix", "")),
        sanitize=bool(merged.get("sanitize", True)),
        separator=str(merged.get("separator", "-")),
        max_length=int(merged.get("max_length", 0)),
    )


def apply_node_rename(
    proxies: list[dict[str, Any]],
    source_name: str,
    rename_cfg: RenameConfig | None = None,
) -> list[dict[str, Any]]:
    """Apply sanitization and prefix to a batch of subscription nodes.

    - Skips nodes without a ``name``.
    - When ``sanitize=True``, calls ``sanitize_node_name`` and drops empties.
    - When name changes by ≥ 3 chars, prints a warning to stderr.
    - Returns a new list; original dicts are not mutated.
    """
    cfg = rename_cfg or RenameConfig()
    prefix = cfg.prefix if cfg.prefix else source_name
    sep = cfg.separator

    result: list[dict[str, Any]] = []
    for proxy in proxies:
        original_name = proxy.get("name", "") or ""
        if not original_name:
            continue

        if cfg.sanitize:
            cleaned = sanitize_node_name(original_name)
            if not cleaned:
                print(
                    f"  [{source_name}] ⚠ sanitize: 节点名清洗后为空，丢弃: {original_name!r}",
                    file=sys.stderr,
                )
                continue
            if len(original_name) - len(cleaned) >= 3:
                print(
                    f"  [{source_name}] ⚠ sanitize: 节点名大幅变形 {original_name!r} → {cleaned!r}",
                    file=sys.stderr,
                )
        else:
            cleaned = original_name

        new_name = f"{prefix}{sep}{cleaned}" if prefix else cleaned
        if cfg.max_length and len(new_name) > cfg.max_length:
            new_name = new_name[:cfg.max_length]
        new_proxy = dict(proxy)
        new_proxy["name"] = new_name
        result.append(new_proxy)

    return result


# ── Filtering / dedup / validation helpers ──────────────────────────────────


def in_benchmark_range(server: str) -> bool:
    """Return whether ``server`` is in 198.18.0.0/15 benchmark/fake-IP range."""
    try:
        parts = server.split(".")
        if len(parts) != 4:
            return False
        return int(parts[0]) == _BENCHMARK_RANGE_PREFIX[0] and int(parts[1]) in _BENCHMARK_RANGE_PREFIX[1]
    except (ValueError, AttributeError):
        return False


def valid_proxies(proxies: list[dict]) -> list[dict]:
    """Drop known placeholder or unusable proxy entries."""
    result: list[dict] = []
    for p in proxies:
        server = p.get("server", "")
        name = p.get("name", "")
        if server in {"127.0.0.1", "localhost", ""} or not name:
            continue
        if server == "8.8.8.8":
            continue
        if in_benchmark_range(server):
            continue
        result.append(p)
    return result


def filter_proxies(
    proxies: list[dict[str, Any]],
    *,
    exclude_keywords: list[str],
    include_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter proxies by include/exclude keywords (deputy extension)."""
    include_keywords = include_keywords or []
    if not exclude_keywords and not include_keywords:
        return list(proxies)
    out: list[dict[str, Any]] = []
    for p in proxies:
        name = p.get("name", "") or ""
        if include_keywords and not any(kw in name for kw in include_keywords):
            continue
        if exclude_keywords and any(kw in name for kw in exclude_keywords):
            continue
        out.append(p)
    return out


def deduplicate_proxies(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by (server, port), preserving first occurrence."""
    seen: set = set()
    out: list[dict[str, Any]] = []
    for p in proxies:
        key = (p.get("server"), p.get("port"))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def proxy_names(proxies) -> list[str]:
    """Return non-empty proxy names."""
    return [p["name"] for p in proxies if p.get("name")]


def compute_dialer_names(alive_subscription_proxies) -> list[str]:
    """Return sorted unique dialer names from alive subscription nodes."""
    sorted_alive = sorted(alive_subscription_proxies, key=lambda p: p.get("name", ""))

    dialer: list[str] = []
    seen: set = set()
    for p in sorted_alive:
        name = p.get("name")
        if name and name not in seen:
            dialer.append(name)
            seen.add(name)

    return dialer


def group_by_source(pairs: list[tuple[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Group ``(source_name, proxy)`` pairs by source name."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for name, proxy in pairs:
        grouped.setdefault(name, []).append(proxy)
    return grouped


def merge_proxy_sets(
    manual_proxies: list[dict],
    alive_subscription_proxies: list[dict],
) -> MergeResult:
    """Merge manual (static) proxies with alive subscription proxies.

    Local proxies keep ``proxies.yaml`` order; subscription proxies are
    deduplicated and sorted by name; duplicates by ``name`` against local
    proxies are removed from the subscription set.
    """
    local_proxies = deduplicate_proxies(manual_proxies)
    local_names = set(proxy_names(local_proxies))
    sub_proxies = [
        p
        for p in deduplicate_proxies(alive_subscription_proxies)
        if p.get("name") not in local_names
    ]
    sub_proxies.sort(key=lambda p: p.get("name", ""))
    return MergeResult(
        local_proxies=local_proxies,
        sub_proxies=sub_proxies,
        dialer_names=compute_dialer_names(sub_proxies),
    )

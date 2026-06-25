"""Subscription source fetching, validation, YAML sanitization, and cache fallback.

Mirrors mihomo-config's ``sources/subscription.py``:
- Strips ANSI/C1 control characters that some CDNs inject.
- Caches last successful validated proxies under ``subscriptions/<source>.yaml``.
- Falls back to the cache when a fetch error is classified as temporary.
- Returns a ``SubscriptionFetchResult`` describing the fetch outcome.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from deputy.sources.config import FetchConfig
from deputy.transport.chain import (
    TransportChain,
    TransportError,
    _is_challenge,
)
from deputy.transport.impls.cloudscraper import CloudscraperTransport
from deputy.transport.impls.curl_cffi import CurlCffiSafariTransport, CurlCffiTransport
from deputy.transport.impls.mihomo import MihomoTransport
from deputy.transport.impls.requests import RequestsTransport
from deputy.transport.impls.tls_client import TlsClientTransport


CACHE_DIR = Path("subscriptions")
_CACHE_PREFIX_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class SubscriptionFetchResult:
    source: str
    proxies: list[dict]
    status: str  # "fresh" | "fallback" | "failed"
    cache_status: str  # "updated" | "unchanged" | "fallback" | "none"
    updated_at: str | None = None


def cache_path(cache_dir: Path | str, prefix: str) -> Path:
    """Return the cache path for a subscription prefix."""
    if not prefix or not _CACHE_PREFIX_SAFE.match(prefix):
        raise ValueError(f"unsafe cache prefix: {prefix!r}")
    return Path(cache_dir) / f"{prefix}.yaml"


def redact_url_tokens(text: str | Exception) -> str:
    """Redact common URL token query values before logging."""
    return re.sub(r"([?&](?:token|access_token)=)[^&\s]+", r"\1***", str(text))


def _yaml_dump(data: dict) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        allow_unicode=True,
    )


def load_subscription_cache(cache_dir: Path | str, prefix: str) -> tuple[list[dict], str | None]:
    """Load cached proxies for one subscription source."""
    path = cache_path(cache_dir, prefix)
    if not path.exists():
        return [], None
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return [], None
    if data.get("source") != prefix:
        return [], None
    proxies = data.get("proxies")
    if not isinstance(proxies, list):
        return [], None
    return proxies, data.get("updated_at")


def save_subscription_cache(
    cache_dir: Path | str,
    prefix: str,
    proxies: list[dict],
    now_fn: Callable[[], str] | None = None,
) -> bool:
    """Save last successful validated proxies for one subscription source."""
    cached, _ = load_subscription_cache(cache_dir, prefix)
    if cached == proxies:
        return False

    path = cache_path(cache_dir, prefix)
    path.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    ts = (now_fn or (lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")))()
    payload = {
        "source": prefix,
        "updated_at": ts,
        "proxies": proxies,
    }
    path.write_text(_yaml_dump(payload))
    return True


def prune_subscription_caches(cache_dir: Path | str, active_sources) -> list[str]:
    """Remove cached subscription files that are no longer configured."""
    cache_dir = Path(cache_dir)
    active_sources = set(active_sources)
    if not cache_dir.exists():
        return []

    removed = []
    for path in sorted(cache_dir.glob("*.yaml")):
        source = path.stem
        if source in active_sources:
            continue
        path.unlink()
        removed.append(source)
    return removed


_ANSI_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]")


def load_clash_subscription_yaml(text: str) -> dict:
    """Parse and validate the minimal Clash subscription shape we consume."""
    text = _ANSI_RE.sub("", text)
    data = yaml.safe_load(text)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("subscription YAML root must be a mapping")
    proxies = data.get("proxies", [])
    if not isinstance(proxies, list):
        raise ValueError("subscription YAML field 'proxies' must be a list")
    return data


def add_clash_flag(sub_url: str) -> str:
    """Append the Clash format flag to a subscription URL."""
    sep = "&" if "?" in sub_url else "?"
    return f"{sub_url}{sep}flag=clash"


def default_transports() -> list:
    """Return the production transport chain order."""
    return [
        MihomoTransport(),
        CloudscraperTransport(),
        RequestsTransport(),
        CurlCffiTransport(),
        CurlCffiSafariTransport(),
        TlsClientTransport(),
    ]


def _sanitize_proxies(
    raw_proxies: list[dict],
    prefix: str | None,
    source_name: str,
) -> list[dict]:
    """Drop nameless / empty-name entries after prefixing with the source.

    Sanitization (cleaning emojis/punctuation/whitespace) is handled later by
    ``deputy.core.nodes.sanitize_node_name``; here we only attach the prefix.
    """
    sanitized: list[dict] = []
    for proxy in raw_proxies:
        original_name = proxy.get("name", "")
        if not original_name:
            continue
        proxy = dict(proxy)
        proxy["name"] = f"{prefix}-{original_name}" if prefix else original_name
        sanitized.append(proxy)
    return sanitized


def fetch_clash_subscription(
    sub_url: str,
    prefix: str | None = None,
    fetch_cfg: FetchConfig | dict | None = None,
    *,
    transport_chain: TransportChain | None = None,
) -> list[dict]:
    """Fetch a Clash subscription and return sanitized valid proxies."""
    url = add_clash_flag(sub_url)

    if transport_chain is None:
        cfg = fetch_cfg or {}
        chain = TransportChain(
            default_transports(),
            max_attempts_per_transport=cfg.get("max_attempts_per_transport", 4),
            max_total_attempts=cfg.get("max_total_attempts", 20),
            base_delay=cfg.get("base_delay", 0.5),
            max_delay=cfg.get("max_delay", 8.0),
            jitter_range=cfg.get("jitter_range", 0.3),
        )
    else:
        chain = transport_chain

    def validate_subscription_response(response) -> None:
        load_clash_subscription_yaml(response.text())

    resp = chain.fetch(url, timeout=getattr(fetch_cfg, "timeout", 45) if fetch_cfg else 45)
    data = load_clash_subscription_yaml(resp.text())

    if _is_challenge(resp.text()):
        raise TransportError("subscription response was a Cloudflare challenge page", retryable=True)

    return _sanitize_proxies(data.get("proxies", []), prefix, prefix or "subscription")


def fetch_subscription_with_cache(
    sub_url: str,
    prefix: str,
    cache_dir: Path | str = CACHE_DIR,
    fetch_fn: Callable | None = None,
    now_fn: Callable[[], str] | None = None,
    fetch_cfg: FetchConfig | dict | None = None,
    *,
    transport_chain: TransportChain | None = None,
) -> SubscriptionFetchResult:
    """Fetch one subscription source, falling back to its last successful cache."""
    source = prefix or "subscription"
    fetch_fn = fetch_fn or fetch_clash_subscription
    try:
        kwargs = {"transport_chain": transport_chain} if transport_chain is not None else {}
        proxies = fetch_fn(sub_url, prefix, fetch_cfg, **kwargs) if fetch_cfg is not None else fetch_fn(sub_url, prefix, **kwargs)
        if not proxies:
            raise RuntimeError("fresh fetch returned 0 valid proxies")
        changed = save_subscription_cache(cache_dir, source, proxies, now_fn=now_fn)
        cache_status = "updated" if changed else "unchanged"
        return SubscriptionFetchResult(source, proxies, "fresh", cache_status)
    except Exception as exc:
        cached, updated_at = load_subscription_cache(cache_dir, source)
        if cached:
            return SubscriptionFetchResult(source, cached, "fallback", "fallback", updated_at)
        return SubscriptionFetchResult(source, [], "failed", "none", None)

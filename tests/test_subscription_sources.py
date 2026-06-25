"""Tests for subscription source fetching, cache, and YAML sanitization."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from deputy.sources.subscription import (
    SubscriptionFetchResult,
    add_clash_flag,
    cache_path,
    load_clash_subscription_yaml,
    load_subscription_cache,
    prune_subscription_caches,
    redact_url_tokens,
    save_subscription_cache,
)


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "test_subscription.yaml"


def test_cache_path_safe_prefix():
    p = cache_path("/tmp/cache", "anaer")
    assert str(p).endswith("anaer.yaml")


def test_cache_path_escapes_unsafe_prefix():
    """Path-traversal and non-ASCII characters are sanitized to underscores."""
    p = cache_path("/tmp/cache", "../etc/passwd")
    # Leading dots are stripped to avoid hidden-file / path-traversal issues
    assert not Path(p).name.startswith(".")
    assert str(p).endswith("_etc_passwd.yaml")


def test_cache_path_handles_cjk_prefix():
    """Chinese source names are safely mapped to filesystem names."""
    p = cache_path("/tmp/cache", "一元")
    assert str(p).endswith("__.yaml")


def test_redact_url_tokens_strips_token_query():
    s = "https://example.com/sub?token=abc&flag=clash"
    out = redact_url_tokens(s)
    assert "***" in out
    assert "token=***" in out


def test_load_clash_subscription_yaml_strips_ansi():
    """ANSI escape sequences (CSI) preceding the YAML body must be stripped."""
    # ESC alone (the C0 control byte that introduces ANSI sequences) should
    # be removed without affecting the rest of the YAML body.
    text = "\x1bport: 7890\nproxies: []\n"
    data = load_clash_subscription_yaml(text)
    assert data["port"] == 7890
    assert data["proxies"] == []


def test_load_clash_subscription_yaml_strips_control_characters():
    """Pure control characters (no CSI payload) must be stripped silently."""
    text = "\x00\x07port: 7890\nproxies: []\n"
    data = load_clash_subscription_yaml(text)
    assert data["port"] == 7890
    assert data["proxies"] == []


def test_load_clash_subscription_yaml_strips_c1_control_characters():
    """C1 control characters in the 0x80-0x9F range must be stripped."""
    text = "\x9b\x9cport: 7890\nproxies: []\n"
    data = load_clash_subscription_yaml(text)
    assert data["port"] == 7890
    assert data["proxies"] == []


def test_load_clash_subscription_yaml_preserves_inner_brackets():
    """Brackets inside the YAML payload are NOT escaped by ANSI stripping."""
    text = "port: 7890\nproxies:\n  - {name: a, type: ss, server: 1.1.1.1, port: 1}\n"
    data = load_clash_subscription_yaml(text)
    assert len(data["proxies"]) == 1
    assert data["proxies"][0]["port"] == 1


def test_load_clash_subscription_yaml_rejects_non_mapping_root():
    with pytest.raises(ValueError, match="root must be a mapping"):
        load_clash_subscription_yaml("- 1\n- 2\n")


def test_load_clash_subscription_yaml_rejects_non_list_proxies():
    with pytest.raises(ValueError, match="'proxies' must be a list"):
        load_clash_subscription_yaml("proxies: not-a-list\n")


def test_add_clash_flag_appends_with_correct_separator():
    assert add_clash_flag("https://example.com/sub").endswith("?flag=clash")
    assert add_clash_flag("https://example.com/sub?token=x").endswith("&flag=clash")


def test_save_and_load_cache_roundtrip(tmp_path: Path):
    proxies = [{"name": "hk-1", "type": "vmess"}]
    changed = save_subscription_cache(tmp_path, "anaer", proxies, now_fn=lambda: "2024-01-01T00:00:00Z")
    assert changed is True
    cached, ts = load_subscription_cache(tmp_path, "anaer")
    assert cached == proxies
    assert ts == "2024-01-01T00:00:00Z"


def test_save_cache_is_idempotent(tmp_path: Path):
    proxies = [{"name": "hk-1"}]
    save_subscription_cache(tmp_path, "anaer", proxies)
    second = save_subscription_cache(tmp_path, "anaer", proxies)
    assert second is False


def test_prune_subscription_caches_removes_unknown_sources(tmp_path: Path):
    save_subscription_cache(tmp_path, "keep", [{"name": "x"}])
    save_subscription_cache(tmp_path, "drop", [{"name": "y"}])
    removed = prune_subscription_caches(tmp_path, ["keep"])
    assert removed == ["drop"]
    assert (tmp_path / "drop.yaml").exists() is False
    assert (tmp_path / "keep.yaml").exists() is True


def test_subscription_fetch_result_is_frozen():
    r = SubscriptionFetchResult("src", [{"name": "a"}], "fresh", "updated", "2024-01-01T00:00:00Z")
    with pytest.raises(Exception):
        r.status = "fallback"  # type: ignore[misc]

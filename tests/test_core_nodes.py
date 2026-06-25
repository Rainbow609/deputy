"""Tests for core node helpers: sanitize, rename, filter, dedup, merge."""

from __future__ import annotations

import pytest

from deputy.core.nodes import (
    MergeResult,
    RenameConfig,
    apply_node_rename,
    build_rename_config,
    compute_dialer_names,
    deduplicate_proxies,
    filter_proxies,
    group_by_source,
    in_benchmark_range,
    merge_proxy_sets,
    proxy_names,
    sanitize_node_name,
    valid_proxies,
)


# ── sanitize_node_name ──────────────────────────────────────────────────────


def test_sanitize_strips_pipe():
    assert sanitize_node_name("香港 01 | 专线") == "香港 01 专线"


def test_sanitize_strips_parentheses():
    assert sanitize_node_name("HK (Premium)") == "HK Premium"


def test_sanitize_strips_brackets():
    assert sanitize_node_name("node[1]{test}") == "node1test"


def test_sanitize_strips_angle_brackets():
    assert sanitize_node_name("node<1>") == "node1"


def test_sanitize_strips_flag_emoji():
    assert sanitize_node_name("\U0001F1ED\U0001F0F0 HK01") == "HK01"


def test_sanitize_strips_symbol_emoji():
    assert sanitize_node_name("⚡Fast Node") == "Fast Node"


def test_sanitize_normalizes_fullwidth_space():
    assert sanitize_node_name("香港\u3000专线") == "香港 专线"


def test_sanitize_collapses_whitespace():
    assert sanitize_node_name("HK    01") == "HK 01"


def test_sanitize_strips_edges():
    assert sanitize_node_name("   HK01   ") == "HK01"


def test_sanitize_preserves_cjk():
    assert sanitize_node_name("香港01") == "香港01"


def test_sanitize_preserves_common_identifiers():
    assert sanitize_node_name("node-01_v2.test/prod·HK") == "node-01_v2.test/prod·HK"


def test_sanitize_empty_input():
    assert sanitize_node_name("") == ""


def test_sanitize_idempotent():
    for s in ["香港 01 | 专线", "⚡Fast Node", "node[1]", "  HK  "]:
        once = sanitize_node_name(s)
        twice = sanitize_node_name(once)
        assert once == twice


def test_sanitize_drops_pure_punctuation():
    assert sanitize_node_name("|") == ""
    assert sanitize_node_name("|()") == ""


def test_sanitize_strips_question_mark():
    assert sanitize_node_name("??乌克兰专线-01") == "乌克兰专线-01"


# ── apply_node_rename ───────────────────────────────────────────────────────


def test_apply_basic_prefix():
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert len(result) == 1
    assert result[0]["name"] == "sub1-HK01"


def test_apply_sanitize_and_prefix():
    proxies = [{"name": "|香港", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert result[0]["name"] == "sub1-香港"


def test_apply_drops_empty_after_sanitize():
    proxies = [
        {"name": "|", "server": "1.1.1.1", "port": 443},
        {"name": "alive", "server": "2.2.2.2", "port": 443},
    ]
    result = apply_node_rename(proxies, "sub1")
    assert len(result) == 1
    assert result[0]["name"] == "sub1-alive"


def test_apply_custom_prefix():
    cfg = RenameConfig(prefix="AN")
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "anaer", cfg)
    assert result[0]["name"] == "AN-HK01"


def test_apply_custom_separator():
    cfg = RenameConfig(separator="_")
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1", cfg)
    assert result[0]["name"] == "sub1_HK01"


def test_apply_sanitize_disabled():
    cfg = RenameConfig(sanitize=False)
    proxies = [{"name": "|香港|", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1", cfg)
    assert result[0]["name"] == "sub1-|香港|"


def test_apply_does_not_mutate_original():
    original = {"name": "HK01", "server": "1.1.1.1", "port": 443}
    apply_node_rename([original], "sub1")
    assert original["name"] == "HK01"


def test_apply_skips_nameless_proxies():
    proxies = [{"type": "vmess", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert result == []


def test_apply_deduplicates_duplicate_names():
    """Same cleaned name from different servers gets 01, 02, ... suffix."""
    proxies = [
        {"name": "美国", "server": "1.1.1.1", "port": 443},
        {"name": "美国", "server": "2.2.2.2", "port": 443},
        {"name": "美国", "server": "3.3.3.3", "port": 443},
        {"name": "英国", "server": "4.4.4.4", "port": 443},
    ]
    result = apply_node_rename(proxies, "vxiaov")
    assert result[0]["name"] == "vxiaov-美国"
    assert result[1]["name"] == "vxiaov-美国 01"
    assert result[2]["name"] == "vxiaov-美国 02"
    assert result[3]["name"] == "vxiaov-英国"


def test_apply_deduplicates_with_custom_prefix():
    """Custom prefix + duplicate names still get suffixes."""
    cfg = RenameConfig(prefix="AN")
    proxies = [
        {"name": "HK", "server": "1.1.1.1", "port": 443},
        {"name": "HK", "server": "2.2.2.2", "port": 443},
    ]
    result = apply_node_rename(proxies, "anaer", cfg)
    assert result[0]["name"] == "AN-HK"
    assert result[1]["name"] == "AN-HK 01"


# ── build_rename_config ─────────────────────────────────────────────────────


def test_build_config_defaults_only():
    cfg = build_rename_config({"sanitize": True, "separator": "_"}, None)
    assert cfg.sanitize is True
    assert cfg.separator == "_"
    assert cfg.prefix == ""


def test_build_config_source_overrides_global():
    cfg = build_rename_config(
        {"separator": "-", "sanitize": True},
        {"separator": "_", "prefix": "AN"},
    )
    assert cfg.separator == "_"
    assert cfg.prefix == "AN"
    assert cfg.sanitize is True


def test_build_config_none_none():
    cfg = build_rename_config(None, None)
    assert cfg.prefix == ""
    assert cfg.sanitize is True
    assert cfg.separator == "-"


# ── valid_proxies / filter / dedup / helpers ───────────────────────────────


def test_valid_proxies_drops_placeholders():
    proxies = [
        {"name": "a", "server": "1.1.1.1", "port": 443, "type": "vmess"},
        {"name": "b", "server": "127.0.0.1", "port": 1, "type": "vmess"},
        {"name": "c", "server": "localhost", "port": 1, "type": "vmess"},
        {"name": "d", "server": "8.8.8.8", "port": 1, "type": "vmess"},
        {"name": "e", "server": "198.18.0.1", "port": 1, "type": "vmess"},
        {"name": "f", "server": "", "port": 1, "type": "vmess"},
        {"name": "", "server": "2.2.2.2", "port": 1, "type": "vmess"},
    ]
    out = valid_proxies(proxies)
    assert [p["name"] for p in out] == ["a"]


def test_in_benchmark_range_isolated_helpers():
    assert in_benchmark_range("198.18.5.5")
    assert not in_benchmark_range("198.17.5.5")


def test_filter_proxies_excludes_keywords():
    proxies = [
        {"name": "hk-good", "type": "vmess"},
        {"name": "hk-bad 官网 20倍", "type": "vmess"},
        {"name": "sg-good", "type": "ss"},
    ]
    out = filter_proxies(proxies, exclude_keywords=["官网", "20倍"])
    assert len(out) == 2
    assert all("官网" not in p["name"] for p in out)


def test_filter_proxies_includes_with_include_keywords():
    proxies = [
        {"name": "hk-good"},
        {"name": "us-good"},
        {"name": "sg-good"},
    ]
    out = filter_proxies(proxies, exclude_keywords=[], include_keywords=["hk", "us"])
    assert [p["name"] for p in out] == ["hk-good", "us-good"]


def test_deduplicate_proxies_by_server_port():
    proxies = [
        {"name": "a", "type": "vmess", "server": "1.1.1.1", "port": 443},
        {"name": "b", "type": "vmess", "server": "1.1.1.1", "port": 443},
        {"name": "c", "type": "ss", "server": "2.2.2.2", "port": 8388},
    ]
    out = deduplicate_proxies(proxies)
    assert len(out) == 2
    assert {p["name"] for p in out} == {"a", "c"}


def test_proxy_names_filters_empty():
    names = proxy_names([{"name": "a"}, {"name": ""}, {"name": "b"}])
    assert names == ["a", "b"]


def test_compute_dialer_names_sorted_unique():
    out = compute_dialer_names(
        [
            {"name": "B"},
            {"name": "A"},
            {"name": "B"},  # duplicate
        ]
    )
    assert out == ["A", "B"]


def test_group_by_source_aggregates_pairs():
    pairs = [("a", {"name": "x"}), ("b", {"name": "y"}), ("a", {"name": "z"})]
    grouped = group_by_source(pairs)
    assert sorted(grouped.keys()) == ["a", "b"]
    assert len(grouped["a"]) == 2
    assert len(grouped["b"]) == 1


def test_merge_proxy_sets_deduplicates_against_manual():
    manual = [
        {"name": "static-1", "server": "1.1.1.1", "port": 443, "type": "vmess"},
    ]
    alive_subs = [
        {"name": "static-1", "server": "1.1.1.1", "port": 443, "type": "vmess"},
        {"name": "sub-2", "server": "2.2.2.2", "port": 443, "type": "vmess"},
        {"name": "sub-1", "server": "3.3.3.3", "port": 443, "type": "vmess"},
    ]
    result = merge_proxy_sets(manual, alive_subs)
    assert isinstance(result, MergeResult)
    assert [p["name"] for p in result.local_proxies] == ["static-1"]
    assert [p["name"] for p in result.sub_proxies] == ["sub-1", "sub-2"]
    assert result.dialer_names == ["sub-1", "sub-2"]

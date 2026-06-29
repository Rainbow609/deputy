"""Tests for the template renderer — ported from deputy + extended."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deputy.rendering.config import (
    _safe_format_map,
    _quote_if_needed,
    generate_proxy_items_yaml,
    generate_proxies_yaml,
    render_template,
)


def test_safe_format_map_replaces_known_keys():
    out = _safe_format_map("Hello {NAME}, you are {AGE}", {"NAME": "Alice", "AGE": 30})
    assert out == "Hello Alice, you are 30"


def test_safe_format_map_preserves_unknown_braces():
    out = _safe_format_map("{ name: foo, type: select }", {"name": "ignored"})
    assert out == "{ name: foo, type: select }"


def test_safe_format_map_case_sensitive():
    out = _safe_format_map("{Node_Select_List}", {"NODE_SELECT_LIST": "x"})
    assert out == "{Node_Select_List}"


def test_render_template_with_all_placeholders(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\ngroups:\n{DIALER_LIST}\n",
        encoding="utf-8",
    )
    out = render_template(
        template,
        local_proxies=[
            {"name": "hk-1", "type": "vmess", "server": "1.1.1.1", "port": 443,
             "uuid": "u", "alterId": 0, "cipher": "auto"}
        ],
        sub_proxies=[
            {"name": "sub-1", "type": "ss", "server": "2.2.2.2", "port": 8388,
             "cipher": "aes-256-gcm", "password": "p"}
        ],
    )
    assert "hk-1" in out
    assert "sub-1" in out


def test_generate_proxy_items_yaml_quotes_special_names():
    proxies = [{"name": "🇸🇬 SG | 專線", "type": "ss", "server": "x",
                "port": 1, "cipher": "a", "password": "p"}]
    out = generate_proxy_items_yaml(proxies)
    assert '"🇸🇬 SG | 專線"' in out


def test_quote_if_needed_handles_empty():
    assert _quote_if_needed("") == '""'


def test_generate_proxies_yaml_emits_full_block():
    items = generate_proxies_yaml([{"name": "a", "type": "ss", "server": "x",
                                    "port": 1, "cipher": "c", "password": "p"}])
    assert items.startswith("proxies:\n  - name: a\n")


def test_generate_proxies_yaml_handles_empty():
    assert generate_proxies_yaml([]) == "proxies: []\n"


def test_render_template_empty_proxy_sections_are_yaml_lists(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text(
        "{PROXIES_BLOCK}"
        "proxy-groups:\n"
        "  - { name: 节点选择, type: select, proxies: [{NODE_SELECT_LIST}] }\n"
        "  - { name: 中转节点, type: url-test, proxies: [{DIALER_LIST}] }\n",
        encoding="utf-8",
    )
    out = render_template(template, local_proxies=[], sub_proxies=[])
    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    assert data["proxies"] == []
    # NODE_SELECT_LIST is prefixed with ``自动选择, `` (mihomo-config parity).
    assert groups["节点选择"]["proxies"] == ["自动选择", "DIRECT"]
    assert groups["中转节点"]["proxies"] == []


def test_render_template_proxy_block_with_nodes_is_valid_yaml(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text(
        "{PROXIES_BLOCK}"
        "proxy-groups:\n"
        "  - { name: 节点选择, type: select, proxies: [{NODE_SELECT_LIST}] }\n"
        "  - { name: 中转节点, type: url-test, proxies: [{DIALER_LIST}] }\n",
        encoding="utf-8",
    )
    out = render_template(
        template,
        local_proxies=[{"name": "static-1", "type": "ss", "server": "1.1.1.1",
                        "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[{"name": "sub-1", "type": "vmess", "server": "2.2.2.2",
                      "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
    )
    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    assert [p["name"] for p in data["proxies"]] == ["static-1", "sub-1"]
    # NODE_SELECT_LIST is prefixed with ``自动选择, `` (mihomo-config parity).
    assert groups["节点选择"]["proxies"] == [
        "自动选择", "static-1", "sub-1", "DIRECT",
    ]
    assert groups["中转节点"]["proxies"] == ["sub-1"]


def test_project_template_renders_with_yaml_anchors():
    """Adopt mihomo-config's anchor/merge-key template style.

    The new config.template.yaml declares ``&pr`` and ``<<: *pr`` merge keys
    to keep the 16 select sub-groups DRY. PyYAML resolves them at parse time,
    so the rendered YAML is still valid mihomo input.
    """
    out = render_template(
        Path("config.template.yaml"),
        local_proxies=[{"name": "static-1", "type": "ss", "server": "1.1.1.1",
                        "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[
            {"name": "sub-hk-1", "type": "vmess", "server": "2.2.2.2",
             "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
            {"name": "sub-jp-1", "type": "vmess", "server": "3.3.3.3",
             "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
        ],
    )
    # Anchor declarations and merge keys are preserved verbatim.
    assert "&pr" in out
    assert "<<: *pr" in out
    # Legacy policy regression check (the old template used &select/*select).
    assert "&select" not in out
    assert "*select" not in out
    # Merged groups inherit proxies from the &pr anchor.
    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    expected_pr_proxies = [
        "自动选择", "香港节点", "日本节点", "美国节点",
        "新加坡节点", "台湾节点", "节点选择", "DIRECT",
    ]
    for name in ("境外AI", "Apple", "Google", "Twitter"):
        assert groups[name]["type"] == "select"
        assert groups[name]["proxies"] == expected_pr_proxies, (
            f"{name} did not inherit &pr proxies correctly"
        )
    # 巴哈姆特 has its own list (not using *pr).
    assert groups["巴哈姆特"]["proxies"] == ["台湾节点", "香港节点", "节点选择"]
    # Regional url-test groups present.
    for region in ("香港节点", "日本节点", "美国节点",
                   "新加坡节点", "台湾节点", "自动选择"):
        assert region in groups, f"missing group {region}"
    # Singular rule-provider path adopted from mihomo-config.
    assert "./rule_provider/AWAvenue-Ads.yaml" in out
    assert "./rule_providers/" not in out
    # Inline timeout/tolerance removed from 中转节点 (moved to p: block).
    assert groups["中转节点"]["url"] == "https://cp.cloudflare.com"
    assert "timeout: 1000" not in str(groups["中转节点"])


def test_region_lists_fall_back_to_direct_when_empty(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text(
        "hk: {HK_LIST}\njp: {JP_LIST}\nus: {US_LIST}\n"
        "sg: {SG_LIST}\ntw: {TW_LIST}\n",
        encoding="utf-8",
    )
    out = render_template(
        template,
        local_proxies=[{"name": "no-region-1", "type": "ss",
                        "server": "1.1.1.1", "port": 8388,
                        "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[],
    )
    # All five regions should fall back to DIRECT when no proxy matches.
    assert "hk: DIRECT" in out
    assert "jp: DIRECT" in out
    assert "us: DIRECT" in out
    assert "sg: DIRECT" in out
    assert "tw: DIRECT" in out


def test_region_lists_partition_by_regex(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text("hk: {HK_LIST}\njp: {JP_LIST}\n", encoding="utf-8")
    out = render_template(
        template,
        local_proxies=[],
        sub_proxies=[
            {"name": "香港 01", "type": "ss", "server": "1.1.1.1",
             "port": 1, "cipher": "c", "password": "p"},
            {"name": "HK | Premium", "type": "ss", "server": "2.2.2.2",
             "port": 1, "cipher": "c", "password": "p"},
            {"name": "JP-Tokyo", "type": "ss", "server": "3.3.3.3",
             "port": 1, "cipher": "c", "password": "p"},
        ],
    )
    # Names with special chars (space, |) get quoted by _quote_if_needed;
    # JP-Tokyo has no special chars, so it stays unquoted.
    assert '"香港 01"' in out
    assert '"HK | Premium"' in out
    # JP bucket must contain only JP nodes (no HK leak).
    jp_line = [line for line in out.split("\n") if line.startswith("jp:")][0]
    assert "JP-Tokyo" in jp_line
    assert "香港" not in jp_line
    assert "HK | Premium" not in jp_line
    # HK bucket must contain only HK nodes (no JP leak).
    hk_line = [line for line in out.split("\n") if line.startswith("hk:")][0]
    assert "香港 01" in hk_line
    assert "HK | Premium" in hk_line
    assert "JP-Tokyo" not in hk_line


def test_node_select_list_prepends_auto_select(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text("p: [{NODE_SELECT_LIST}]", encoding="utf-8")
    out = render_template(
        template,
        local_proxies=[{"name": "static-1", "type": "ss",
                        "server": "1.1.1.1", "port": 1,
                        "cipher": "c", "password": "p"}],
        sub_proxies=[],
    )
    # First proxy in the rendered list must be 自动选择 (mihomo-config parity).
    assert out.startswith("p: [自动选择, static-1, DIRECT]")


def test_render_template_with_extra_replacements(tmp_path: Path):
    template = tmp_path / "t.yaml"
    template.write_text("v: {CUSTOM}", encoding="utf-8")
    out = render_template(
        template,
        local_proxies=[],
        sub_proxies=[],
        extra_replacements={"CUSTOM": "hello"},
    )
    assert out == "v: hello"

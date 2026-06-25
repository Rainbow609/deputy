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
    assert groups["节点选择"]["proxies"] == ["DIRECT"]
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
    assert groups["节点选择"]["proxies"] == ["static-1", "sub-1", "DIRECT"]
    assert groups["中转节点"]["proxies"] == ["sub-1"]


def test_project_template_renders_without_yaml_anchors():
    out = render_template(
        Path("config.template.yaml"),
        local_proxies=[{"name": "static-1", "type": "ss", "server": "1.1.1.1",
                        "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[{"name": "sub-1", "type": "vmess", "server": "2.2.2.2",
                      "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
    )
    assert "&select" not in out
    assert "*select" not in out
    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    assert groups["节点选择"]["proxies"][0] == "static-1"
    assert groups["中转节点"]["url"] == "https://cp.cloudflare.com"


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

"""Tests for template renderer — port of mihomo-config _safe_format_map."""

from scripts.template_renderer import (
    render_template,
    _safe_format_map,
    generate_proxy_items_yaml,
)
import yaml


def test_safe_format_map_replaces_known_keys():
    out = _safe_format_map("Hello {NAME}, you are {AGE}", {"NAME": "Alice", "AGE": 30})
    assert out == "Hello Alice, you are 30"


def test_safe_format_map_preserves_unknown_braces():
    """Flow-style YAML uses {name: ...} — those must be left alone."""
    out = _safe_format_map("{ name: foo, type: select }", {"name": "ignored"})
    assert out == "{ name: foo, type: select }"


def test_safe_format_map_case_sensitive():
    out = _safe_format_map("{Node_Select_List}", {"NODE_SELECT_LIST": "x"})
    assert out == "{Node_Select_List}"  # lowercase prefix is not a placeholder


def test_render_template_with_all_placeholders(tmp_path):
    template = tmp_path / "t.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\ngroups:\n{DIALER_LIST}\n",
        encoding="utf-8",
    )
    out = render_template(
        template,
        local_proxies=[{"name": "hk-1", "type": "vmess", "server": "1.1.1.1", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
        sub_proxies=[{"name": "sub-1", "type": "ss", "server": "2.2.2.2", "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
    )
    assert "hk-1" in out
    assert "sub-1" in out


def test_generate_proxy_items_yaml_quotes_special_names():
    proxies = [{"name": "🇸🇬 SG | 專線", "type": "ss", "server": "x", "port": 1, "cipher": "a", "password": "p"}]
    out = generate_proxy_items_yaml(proxies)
    # Special chars must be wrapped in double quotes to satisfy mihomo parser
    assert '"🇸🇬 SG | 專線"' in out


def test_render_template_empty_proxy_sections_are_yaml_lists(tmp_path):
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


def test_render_template_proxy_block_with_nodes_is_valid_yaml(tmp_path):
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
        local_proxies=[{"name": "static-1", "type": "ss", "server": "1.1.1.1", "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[{"name": "sub-1", "type": "vmess", "server": "2.2.2.2", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
    )

    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    assert [p["name"] for p in data["proxies"]] == ["static-1", "sub-1"]
    assert groups["节点选择"]["proxies"] == ["static-1", "sub-1", "DIRECT"]
    assert groups["中转节点"]["proxies"] == ["sub-1"]


def test_project_template_renders_without_yaml_anchors():
    out = render_template(
        __import__("pathlib").Path("config.template.yaml"),
        local_proxies=[{"name": "static-1", "type": "ss", "server": "1.1.1.1", "port": 8388, "cipher": "aes-256-gcm", "password": "p"}],
        sub_proxies=[{"name": "sub-1", "type": "vmess", "server": "2.2.2.2", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
    )
    assert "&select" not in out
    assert "*select" not in out

    data = yaml.safe_load(out)
    groups = {g["name"]: g for g in data["proxy-groups"]}
    assert groups["Apple"]["proxies"] == ["节点选择", "DIRECT"]
    assert groups["Twitter"]["proxies"] == ["节点选择"]

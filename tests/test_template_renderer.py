"""Tests for template renderer — port of mihomo-config _safe_format_map."""

from scripts.template_renderer import (
    render_template,
    _safe_format_map,
    generate_proxy_items_yaml,
)


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

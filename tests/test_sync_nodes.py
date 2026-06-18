"""Tests for scripts.sync_nodes helper functions.

These tests focus on the pure helper functions (parse, filter, deduplicate,
load_previous_config) so we can validate their behavior without depending on
network or filesystem side effects of the full run_sync pipeline.
"""

import sys
from pathlib import Path

import yaml

# Make the project root importable when pytest is invoked from the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sync_nodes import (  # noqa: E402
    deduplicate_proxies,
    fetch_subscription_yaml,
    filter_proxies,
    load_previous_config,
    parse_clash_yaml,
)


SAMPLE_CLASH = """
port: 7890
proxies:
  - {name: "hk-1", type: vmess, server: 1.1.1.1, port: 443, uuid: u, alterId: 0, cipher: auto}
  - {name: "sg-1", type: ss, server: 2.2.2.2, port: 8388, cipher: aes-256-gcm, password: p}
  - {name: "  🇸🇬 SG  ", type: ss, server: 3.3.3.3, port: 8388, cipher: aes-256-gcm, password: p}
"""


def test_parse_clash_yaml_extracts_proxies():
    data = parse_clash_yaml(SAMPLE_CLASH)
    assert len(data["proxies"]) == 3
    assert data["proxies"][0]["name"] == "hk-1"


def test_filter_proxies_excludes_keywords():
    proxies = [
        {"name": "hk-good", "type": "vmess"},
        {"name": "hk-bad 官网 20倍", "type": "vmess"},
        {"name": "sg-good", "type": "ss"},
    ]
    out = filter_proxies(proxies, exclude_keywords=["官网", "20倍"])
    assert len(out) == 2
    assert all("官网" not in p["name"] for p in out)


def test_deduplicate_proxies_by_server_port():
    proxies = [
        {"name": "a", "type": "vmess", "server": "1.1.1.1", "port": 443},
        {"name": "b", "type": "vmess", "server": "1.1.1.1", "port": 443},
        {"name": "c", "type": "ss", "server": "2.2.2.2", "port": 8388},
    ]
    out = deduplicate_proxies(proxies)
    assert len(out) == 2
    assert {p["name"] for p in out} == {"a", "c"}


def test_load_previous_config_missing(tmp_path):
    assert load_previous_config(tmp_path / "nope.yaml") == ""


def test_load_previous_config_existing(tmp_path):
    p = tmp_path / "prev.yaml"
    p.write_text("a: 1\n", encoding="utf-8")
    assert load_previous_config(p) == "a: 1\n"

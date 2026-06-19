"""Tests for scripts.node_renamer module.

Covers:
- sanitize_node_name pure function (ported from mihomo-config)
- apply_node_rename with prefix + sanitize
- build_rename_config merging logic
"""

import sys
from pathlib import Path

# Make the project root importable when pytest is invoked from the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.node_renamer import (  # noqa: E402
    RenameConfig,
    apply_node_rename,
    build_rename_config,
    sanitize_node_name,
)


# ── sanitize_node_name 纯函数测试 ────────────────────────────────────


def test_sanitize_strips_pipe():
    """ASCII 管道符 | 被去除。"""
    assert sanitize_node_name("香港 01 | 专线") == "香港 01 专线"


def test_sanitize_strips_parentheses():
    """半角圆括号被去除。"""
    assert sanitize_node_name("HK (Premium)") == "HK Premium"


def test_sanitize_strips_brackets():
    """方括号与花括号被去除。"""
    assert sanitize_node_name("node[1]{test}") == "node1test"


def test_sanitize_strips_angle_brackets():
    """尖括号被去除。"""
    assert sanitize_node_name("node<1>") == "node1"


def test_sanitize_strips_flag_emoji():
    """旗帜 emoji（区域指示符，So 类别）被去除。"""
    assert sanitize_node_name("\U0001F1ED\U0001F0F0 HK01") == "HK01"


def test_sanitize_strips_symbol_emoji():
    """装饰符号 emoji（⚡，So 类别）被去除。"""
    assert sanitize_node_name("⚡Fast Node") == "Fast Node"


def test_sanitize_normalizes_fullwidth_space():
    """全角空格 U+3000 折叠为半角空格。"""
    assert sanitize_node_name("香港\u3000专线") == "香港 专线"


def test_sanitize_collapses_whitespace():
    """多个连续半角空格折叠为单个。"""
    assert sanitize_node_name("HK    01") == "HK 01"


def test_sanitize_strips_edges():
    """首尾空白 strip。"""
    assert sanitize_node_name("   HK01   ") == "HK01"


def test_sanitize_preserves_cjk():
    """中文 + ASCII 数字保留。"""
    assert sanitize_node_name("香港01") == "香港01"


def test_sanitize_preserves_common_identifiers():
    """常用标识符 - _ . / · 保留。"""
    assert sanitize_node_name("node-01_v2.test/prod·HK") == "node-01_v2.test/prod·HK"


def test_sanitize_empty_input():
    """空字符串返回空字符串。"""
    assert sanitize_node_name("") == ""


def test_sanitize_idempotent():
    """相同输入两次返回相等字符串（幂等）。"""
    for s in ["香港 01 | 专线", "⚡Fast Node", "node[1]", "  HK  "]:
        once = sanitize_node_name(s)
        twice = sanitize_node_name(once)
        assert once == twice


def test_sanitize_drops_pure_punctuation():
    """纯标点输入返回空串（caller 负责丢弃节点）。"""
    assert sanitize_node_name("|") == ""
    assert sanitize_node_name("|()") == ""


def test_sanitize_strips_question_mark():
    """问号被去除（上游用 ?? 作节点名前缀装饰）。"""
    assert sanitize_node_name("??乌克兰专线-01") == "乌克兰专线-01"


# ── apply_node_rename 测试 ────────────────────────────────────────────


def test_apply_basic_prefix():
    """默认配置：source_name 作为前缀，sanitize=True。"""
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert len(result) == 1
    assert result[0]["name"] == "sub1-HK01"


def test_apply_sanitize_and_prefix():
    """清洗 + 前缀组合：|香港 → sub1-香港。"""
    proxies = [{"name": "|香港", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert len(result) == 1
    assert result[0]["name"] == "sub1-香港"


def test_apply_drops_empty_after_sanitize():
    """清洗后为空的节点被丢弃。"""
    proxies = [
        {"name": "|", "server": "1.1.1.1", "port": 443},
        {"name": "alive", "server": "2.2.2.2", "port": 443},
    ]
    result = apply_node_rename(proxies, "sub1")
    assert len(result) == 1
    assert result[0]["name"] == "sub1-alive"


def test_apply_custom_prefix():
    """自定义前缀覆盖 source_name。"""
    cfg = RenameConfig(prefix="AN")
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "anaer", cfg)
    assert result[0]["name"] == "AN-HK01"


def test_apply_custom_separator():
    """自定义分隔符。"""
    cfg = RenameConfig(separator="_")
    proxies = [{"name": "HK01", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1", cfg)
    assert result[0]["name"] == "sub1_HK01"


def test_apply_sanitize_disabled():
    """sanitize=False 时不清洗名称，但仍添加前缀。"""
    cfg = RenameConfig(sanitize=False)
    proxies = [{"name": "|香港|", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1", cfg)
    assert result[0]["name"] == "sub1-|香港|"


def test_apply_does_not_mutate_original():
    """不修改原始 proxy dict。"""
    original = {"name": "HK01", "server": "1.1.1.1", "port": 443}
    apply_node_rename([original], "sub1")
    assert original["name"] == "HK01"


def test_apply_skips_nameless_proxies():
    """跳过无 name 字段的节点。"""
    proxies = [{"type": "vmess", "server": "1.1.1.1", "port": 443}]
    result = apply_node_rename(proxies, "sub1")
    assert result == []


# ── build_rename_config 测试 ──────────────────────────────────────────


def test_build_config_defaults_only():
    """仅全局默认，无逐源覆盖。"""
    cfg = build_rename_config({"sanitize": True, "separator": "_"}, None)
    assert cfg.sanitize is True
    assert cfg.separator == "_"
    assert cfg.prefix == ""


def test_build_config_source_overrides_global():
    """逐源覆盖优先于全局默认。"""
    cfg = build_rename_config(
        {"separator": "-", "sanitize": True},
        {"separator": "_", "prefix": "AN"},
    )
    assert cfg.separator == "_"
    assert cfg.prefix == "AN"
    assert cfg.sanitize is True


def test_build_config_none_none():
    """两个均为 None 时返回默认值。"""
    cfg = build_rename_config(None, None)
    assert cfg.prefix == ""
    assert cfg.sanitize is True
    assert cfg.separator == "-"

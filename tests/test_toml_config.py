"""Tests for the TOML config loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from deputy.sources.config import (
    ConfigError,
    FetchConfig,
    load_config,
    write_text_atomic,
)


VALID_TOML = """
[subscription]
format = "clash"
exclude_keywords = ["官网", "到期"]

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[subscription_sources]
"星链云" = "https://example.com/sub?token=abc"
"""


def test_load_valid_config(tmp_path: Path):
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(VALID_TOML, encoding="utf-8")
    config = load_config(config_file)
    assert config.subscription.format == "clash"
    assert config.subscription.exclude_keywords == ["官网", "到期"]
    assert config.probe.timeout == 3
    assert config.probe.concurrency == 30
    assert "星链云" in config.subscription_sources
    # New: default FetchConfig
    assert isinstance(config.fetch, FetchConfig)
    assert config.fetch.max_total_attempts == 20


def test_load_missing_file_raises():
    with pytest.raises(ConfigError, match="配置文件不存在"):
        load_config(Path("/nonexistent/sync_config.toml"))


def test_load_invalid_toml_raises(tmp_path: Path):
    bad_file = tmp_path / "bad.toml"
    bad_file.write_text("this is not = valid toml [", encoding="utf-8")
    with pytest.raises(ConfigError, match="TOML 解析失败"):
        load_config(bad_file)


def test_load_config_without_rename(tmp_path: Path):
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(VALID_TOML, encoding="utf-8")
    config = load_config(config_file)
    assert config.rename == {}


def test_load_config_with_rename_global(tmp_path: Path):
    toml_text = VALID_TOML + """
[rename]
sanitize = true
separator = "_"
"""
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    config = load_config(config_file)
    assert config.rename["sanitize"] is True
    assert config.rename["separator"] == "_"


def test_load_config_with_rename_per_source(tmp_path: Path):
    toml_text = VALID_TOML + """
[rename]
sanitize = true

[rename."星链云"]
prefix = "XL"
separator = "_"
"""
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    config = load_config(config_file)
    assert "星链云" in config.rename
    assert config.rename["星链云"]["prefix"] == "XL"
    assert config.rename["星链云"]["separator"] == "_"


def test_load_config_rejects_non_table_rename(tmp_path: Path):
    toml_text = """
rename = "nope"

[subscription]
format = "clash"
exclude_keywords = ["官网", "到期"]

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[subscription_sources]
"星链云" = "https://example.com/sub?token=abc"
"""
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match="rename"):
        load_config(config_file)


def test_load_config_rejects_invalid_rename_value_types(tmp_path: Path):
    toml_text = VALID_TOML + """
[rename]
sanitize = "false"
separator = 123
"""
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match="rename"):
        load_config(config_file)


def test_load_config_with_fetch_block(tmp_path: Path):
    toml_text = VALID_TOML + """
[subscription.fetch]
base_delay = 0.1
max_delay = 1.0
jitter_range = 0.05
max_attempts_per_transport = 2
max_total_attempts = 8
timeout = 15
"""
    config_file = tmp_path / "sync_config.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    config = load_config(config_file)
    assert config.fetch.base_delay == 0.1
    assert config.fetch.max_total_attempts == 8
    assert config.fetch.timeout == 15


def test_write_text_atomic_replaces_target(tmp_path: Path):
    target = tmp_path / "out.txt"
    target.write_text("old", encoding="utf-8")
    write_text_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_write_text_atomic_cleans_tmp_on_failure(tmp_path: Path):
    target = tmp_path / "out.txt"

    def boom(*_):
        raise RuntimeError("simulated write failure")

    import unittest.mock as um

    with um.patch("deputy.sources.config.os.fdopen", side_effect=boom):
        try:
            write_text_atomic(target, "x")
        except RuntimeError:
            pass
    # tmp files in target.parent should not leave stale junk for long
    leftovers = list(tmp_path.glob(".out.txt.*.tmp"))
    assert leftovers == []

VALID_TOML = """
[subscription]
format = "clash"
exclude_keywords = ["官网", "到期"]

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[subscription_sources]
"星链云" = "https://example.com/sub?token=abc"
"""

def test_load_valid_config(tmp_path: Path):
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(VALID_TOML, encoding="utf-8")
    config = load_config(config_file)
    assert config.subscription.format == "clash"
    assert config.subscription.exclude_keywords == ["官网", "到期"]
    assert config.probe.timeout == 3
    assert config.probe.concurrency == 30
    assert "星链云" in config.subscription_sources

def test_load_missing_file_raises():
    with pytest.raises(ConfigError, match="配置文件不存在"):
        load_config(Path("/nonexistent/nodes.toml"))

def test_load_invalid_toml_raises(tmp_path: Path):
    bad_file = tmp_path / "bad.toml"
    bad_file.write_text("this is not = valid toml [", encoding="utf-8")
    with pytest.raises(ConfigError, match="TOML 解析失败"):
        load_config(bad_file)


def test_load_config_without_rename(tmp_path: Path):
    """无 [rename] 段时 config.rename 为空 dict。"""
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(VALID_TOML, encoding="utf-8")
    config = load_config(config_file)
    assert config.rename == {}


def test_load_config_with_rename_global(tmp_path: Path):
    """有 [rename] 全局段时正确解析。"""
    toml_text = VALID_TOML + """
[rename]
sanitize = true
separator = "_"
"""
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    config = load_config(config_file)
    assert config.rename["sanitize"] is True
    assert config.rename["separator"] == "_"


def test_load_config_with_rename_per_source(tmp_path: Path):
    """逐源覆盖正确解析。"""
    toml_text = VALID_TOML + """
[rename]
sanitize = true

[rename."星链云"]
prefix = "XL"
separator = "_"
"""
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    config = load_config(config_file)
    assert "星链云" in config.rename
    assert config.rename["星链云"]["prefix"] == "XL"
    assert config.rename["星链云"]["separator"] == "_"


def test_load_config_rejects_non_table_rename(tmp_path: Path):
    """[rename] 不是 table 时应报错而不是静默忽略。"""
    toml_text = """
rename = "nope"

[subscription]
format = "clash"
exclude_keywords = ["官网", "到期"]

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[subscription_sources]
"星链云" = "https://example.com/sub?token=abc"
"""
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match="rename"):
        load_config(config_file)


def test_load_config_rejects_invalid_rename_value_types(tmp_path: Path):
    """[rename] 中已知字段类型错误时应报错。"""
    toml_text = VALID_TOML + """
[rename]
sanitize = "false"
separator = 123
"""
    config_file = tmp_path / "nodes.toml"
    config_file.write_text(toml_text, encoding="utf-8")
    with pytest.raises(ConfigError, match="rename"):
        load_config(config_file)

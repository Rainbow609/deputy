import pytest
from pathlib import Path
from scripts.toml_config import load_config, ConfigError

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

"""节点名规范化与重命名模块。

提供与 mihomo-config 一致的节点名清洗逻辑：
- sanitize_node_name：去 ASCII 标点 + 去 emoji/装饰符号 + 折叠空白
- apply_node_rename：批量应用前缀 + 清洗
- build_rename_config：合并全局默认与逐源覆盖
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any


# ── 模块级常量 ──────────────────────────────────────────────────

# 去除 ASCII 标点候选字符
_SANITIZE_ASCII_PUNCT = re.compile(r"[|()\[\]{}<>!@#$%^&*=+`~?]")
# 去除 So (Symbol, other) 与 Sm (Symbol, math) 类别：覆盖旗帜/装饰 emoji
_SANITIZE_SYMBOL_CAT = ("So", "Sm")
# 全角空格 U+3000 → 半角空格
_FULLWIDTH_SPACE = "\u3000"


# ── 公共函数 ────────────────────────────────────────────────────


def sanitize_node_name(name: str) -> str:
    """规范化订阅源节点名：去 ASCII 标点 + 去 emoji/装饰符号 + 折叠空白。

    纯函数：相同输入永远返回相同输出。

    步骤顺序（顺序敏感，每步处理前一未覆盖的字符类）：
    1. 去 ASCII 标点：|()[]{}!@#$%^&*=+`~?
    2. 去 emoji/装饰符号：Unicode 类别为 So/Sm 的字符。
    3. 全角空格 U+3000 → 半角空格。
    4. 连续空白折叠为单个半角空格。
    5. 去除首尾空白。

    返回空字符串时由调用方负责丢弃该节点。
    """
    if not name:
        return ""

    # 1. ASCII 标点
    s = _SANITIZE_ASCII_PUNCT.sub("", name)

    # 2. So / Sm 类别字符（emoji / 装饰符号 / 数学符号）
    s = "".join(c for c in s if unicodedata.category(c) not in _SANITIZE_SYMBOL_CAT)

    # 3. 全角空格 → 半角空格
    s = s.replace(_FULLWIDTH_SPACE, " ")

    # 4. 连续空白折叠为单空格
    s = re.sub(r"\s+", " ", s)

    # 5. 去除首尾空白
    return s.strip()


@dataclass
class RenameConfig:
    """Per-source rename settings."""

    prefix: str = ""
    sanitize: bool = True
    separator: str = "-"


def build_rename_config(
    global_rename: dict[str, Any] | None,
    source_rename: dict[str, Any] | None,
) -> RenameConfig:
    """合并全局默认与逐源覆盖，source 级优先。

    两个参数均为 None 时返回默认 RenameConfig。
    """
    merged: dict[str, Any] = {}
    if global_rename:
        merged.update(global_rename)
    if source_rename:
        merged.update(source_rename)

    return RenameConfig(
        prefix=str(merged.get("prefix", "")),
        sanitize=bool(merged.get("sanitize", True)),
        separator=str(merged.get("separator", "-")),
    )


def apply_node_rename(
    proxies: list[dict[str, Any]],
    source_name: str,
    rename_cfg: RenameConfig | None = None,
) -> list[dict[str, Any]]:
    """对一批订阅节点应用名称清洗和前缀。

    - 跳过 name 为空的节点
    - sanitize=True 时调用 sanitize_node_name；清洗后为空则丢弃
    - 名称变形 ≥3 字符时 log warning
    - 不修改原始 dict，返回新列表
    """
    cfg = rename_cfg or RenameConfig()
    prefix = cfg.prefix if cfg.prefix else source_name
    sep = cfg.separator

    result: list[dict[str, Any]] = []
    for proxy in proxies:
        original_name = proxy.get("name", "") or ""
        if not original_name:
            continue

        if cfg.sanitize:
            cleaned = sanitize_node_name(original_name)
            if not cleaned:
                print(
                    f"  [{source_name}] ⚠ sanitize: 节点名清洗后为空，丢弃: {original_name!r}",
                    file=sys.stderr,
                )
                continue
            if len(original_name) - len(cleaned) >= 3:
                print(
                    f"  [{source_name}] ⚠ sanitize: 节点名大幅变形 {original_name!r} → {cleaned!r}",
                    file=sys.stderr,
                )
        else:
            cleaned = original_name

        new_proxy = dict(proxy)
        new_proxy["name"] = f"{prefix}{sep}{cleaned}" if prefix else cleaned
        result.append(new_proxy)

    return result

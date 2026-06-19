"""Template renderer for Clash Meta config.

Direct port of mihomo-config's _safe_format_map. Only uppercase-brace
identifiers (e.g. {LOCAL_PROXIES}) are treated as placeholders; flow-style
YAML like `{ name: ... }` is left untouched to avoid breaking the
generated config.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable


_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")


def _safe_format_map(template_text: str, mapping: dict[str, str]) -> str:
    """Replace {KEY} only when KEY is in mapping; preserve other braces."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping:
            return str(mapping[key])
        return match.group(0)

    return _PLACEHOLDER_PATTERN.sub(repl, template_text)


_SPECIAL_NAME_CHARS = set(" \t#&*!|>'\"%@`,[]{}()") | {chr(c) for c in range(0x1F300, 0x1FAFF)}


def _quote_if_needed(name: str) -> str:
    """Wrap a node name in double quotes if it contains special characters.

    Mihomo rejects unquoted names like "🇸🇬 SG | 專線" with a parse error.
    """
    if not name or any(ch in _SPECIAL_NAME_CHARS for ch in name):
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return name


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if any(ch in value for ch in [":", "#", "\n", '"']) or value.strip() != value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value
    return str(value)


def generate_proxy_items_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    """Serialize proxy dicts to YAML, quoting special-char names."""
    lines: list[str] = []
    for p in proxies:
        if not p.get("name"):
            continue
        quoted_name = _quote_if_needed(p["name"])
        fields: list[str] = []
        for k, v in p.items():
            if k == "name":
                continue
            fields.append(f"    {k}: {_yaml_scalar(v)}")
        body = "\n".join(fields)
        lines.append(f"  - name: {quoted_name}\n{body}")
    return "\n".join(lines) + ("\n" if lines else "")


def _generate_proxy_list_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    return generate_proxy_items_yaml(proxies) or "[]\n"


def _generate_proxy_block_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    items = generate_proxy_items_yaml(proxies)
    if not items:
        return "proxies: []\n"
    return f"proxies:\n{items}"


def render_template(
    template_path: Path,
    local_proxies: list[dict[str, Any]],
    sub_proxies: list[dict[str, Any]] | None = None,
    extra_replacements: dict[str, str] | None = None,
) -> str:
    """Render the template at `template_path` by substituting placeholders.

    Available placeholders:
    - {LOCAL_PROXIES}: YAML list of static proxies
    - {SUB_PROXIES}: YAML list of subscription proxies
    - {PROXIES}: YAML list of all proxies combined
    - {PROXIES_BLOCK}: complete `proxies` YAML field
    - {NODE_SELECT_LIST}: comma-separated proxy names for `select` groups
    - {DIALER_LIST}: comma-separated subscription proxy names
    """
    text = template_path.read_text(encoding="utf-8")
    sub_proxies = sub_proxies or []
    all_proxies = list(local_proxies) + list(sub_proxies)
    names = [p["name"] for p in all_proxies if p.get("name")]
    if "DIRECT" not in names:
        names.append("DIRECT")
    node_list = ", ".join(_quote_if_needed(n) for n in names)
    dialer_names = [p["name"] for p in sub_proxies if p.get("name")]
    dialer_list = ", ".join(_quote_if_needed(n) for n in sorted(dialer_names))

    mapping = {
        "LOCAL_PROXIES": generate_proxy_items_yaml(local_proxies),
        "SUB_PROXIES": generate_proxy_items_yaml(sub_proxies),
        "PROXIES": _generate_proxy_list_yaml(all_proxies),
        "PROXIES_BLOCK": _generate_proxy_block_yaml(all_proxies),
        "NODE_SELECT_LIST": node_list,
        "DIALER_LIST": dialer_list,
    }
    if extra_replacements:
        mapping.update(extra_replacements)
    return _safe_format_map(text, mapping)

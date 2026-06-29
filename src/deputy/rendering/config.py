"""Render mihomo config text from template and proxy data."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import yaml


_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")

_SPECIAL_NAME_CHARS = set(" \t#&*!|>'\"%@`,[]{}()") | {chr(c) for c in range(0x1F300, 0x1FAFF)}

# Region regex patterns used to bucket proxy names for the regional url-test
# groups (``{HK_LIST}``/``{JP_LIST}``/``{US_LIST}``/``{SG_LIST}``/``{TW_LIST}``).
# Mirrors ``deputy.utils.summary.region_counts`` so renderer and metrics
# agree on what counts as "HK" / "JP" / etc.
_REGION_PATTERNS: dict[str, re.Pattern[str]] = {
    "HK": re.compile(r"(?i)香港|HK|Hong"),
    "JP": re.compile(r"(?i)日本|JP|Japan"),
    "US": re.compile(r"(?i)美国|US|United States"),
    "SG": re.compile(r"(?i)新加坡|SG|Singapore"),
    "TW": re.compile(r"(?i)台湾|TW|Taiwan"),
}


def _safe_format_map(template_text: str, mapping: dict[str, str]) -> str:
    """Replace {KEY} only when KEY is in mapping; preserve other braces."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping:
            return str(mapping[key])
        return match.group(0)

    return _PLACEHOLDER_PATTERN.sub(repl, template_text)


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
        if any(ch in value for ch in [":", "#", "\n", '"', "%"]) or value.strip() != value:
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


def generate_proxies_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    """Generate the full ``proxies:`` YAML block.

    Identical output to ``generate_proxy_items_yaml`` but with the leading
    ``proxies:`` key, suitable for direct substitution into a template that
    uses a single ``{PROXIES}`` placeholder.
    """
    items = generate_proxy_items_yaml(proxies)
    if not items:
        return "proxies: []\n"
    return f"proxies:\n{items}"


def _generate_proxy_list_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    items = generate_proxy_items_yaml(proxies)
    if not items:
        return "[]\n"
    return items


def _generate_proxy_block_yaml(proxies: Iterable[dict[str, Any]]) -> str:
    items = generate_proxy_items_yaml(proxies)
    if not items:
        return "proxies: []\n"
    return f"proxies:\n{items}"


def _region_lists(names: Iterable[str]) -> dict[str, str]:
    """Bucket proxy names by region for the regional url-test groups.

    Each name is assigned to the first region whose regex matches. Empty
    buckets fall back to ``DIRECT`` so the rendered template always has at
    least one proxy in each regional url-test group (matches mihomo-config
    behaviour; prevents mihomo from failing to start with an empty group).

    Returns a dict with keys ``HK_LIST`` / ``JP_LIST`` / ``US_LIST`` /
    ``SG_LIST`` / ``TW_LIST`` whose values are comma-separated name lists
    (or the literal ``DIRECT``). Names are passed through
    ``_quote_if_needed`` so special characters (``|``, spaces, emoji,
    etc.) remain valid inside the rendered flow-style YAML list.
    """
    grouped: dict[str, list[str]] = {f"{k}_LIST": [] for k in _REGION_PATTERNS}
    for n in names:
        for key, pat in _REGION_PATTERNS.items():
            if pat.search(n):
                grouped[f"{key}_LIST"].append(n)
                break
    return {
        slot: ", ".join(_quote_if_needed(v) for v in values) if values else "DIRECT"
        for slot, values in grouped.items()
    }


def render_template(
    template_path: Path,
    local_proxies: list[dict[str, Any]],
    sub_proxies: list[dict[str, Any]] | None = None,
    extra_replacements: dict[str, str] | None = None,
) -> str:
    """Render the template at ``template_path`` by substituting placeholders.

    Available placeholders:
    - ``{LOCAL_PROXIES}``: YAML list of static proxies
    - ``{SUB_PROXIES}``: YAML list of subscription proxies
    - ``{PROXIES}``: YAML list of all proxies combined
    - ``{PROXIES_BLOCK}``: complete ``proxies`` YAML field (legacy, kept for
      backwards compatibility with custom templates)
    - ``{NODE_SELECT_LIST}``: comma-separated proxy names for ``select``
      groups, prefixed with ``自动选择, `` (mihomo-config behaviour) so the
      ``节点选择`` group exposes the ``自动选择`` url-test option as a child;
      ``DIRECT`` is appended if not already present
    - ``{DIALER_LIST}``: comma-separated subscription proxy names
    - ``{HK_LIST}`` / ``{JP_LIST}`` / ``{US_LIST}`` / ``{SG_LIST}`` /
      ``{TW_LIST}``: comma-separated proxy names matching each region's
      regex; falls back to ``DIRECT`` when the bucket is empty
    """
    text = template_path.read_text(encoding="utf-8")
    sub_proxies = sub_proxies or []
    all_proxies = list(local_proxies) + list(sub_proxies)
    names = [p["name"] for p in all_proxies if p.get("name")]
    if "DIRECT" not in names:
        names.append("DIRECT")
    # Match mihomo-config: prepend ``自动选择`` so the ``节点选择`` select
    # group exposes the ``自动选择`` url-test option as a child.
    node_list = "自动选择, " + ", ".join(_quote_if_needed(n) for n in names)
    dialer_names = [p["name"] for p in sub_proxies if p.get("name")]
    dialer_list = ", ".join(_quote_if_needed(n) for n in sorted(dialer_names))

    mapping: dict[str, str] = {
        "LOCAL_PROXIES": generate_proxy_items_yaml(local_proxies),
        "SUB_PROXIES": generate_proxy_items_yaml(sub_proxies),
        "PROXIES": _generate_proxy_list_yaml(all_proxies),
        "PROXIES_BLOCK": _generate_proxy_block_yaml(all_proxies),
        "NODE_SELECT_LIST": node_list,
        "DIALER_LIST": dialer_list,
    }
    mapping.update(_region_lists(names))
    if extra_replacements:
        mapping.update(extra_replacements)
    return _safe_format_map(text, mapping)


def yaml_dump(data: Any) -> str:
    """Dump data to YAML with consistent formatting options."""
    return yaml.dump(
        data,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        allow_unicode=True,
    )

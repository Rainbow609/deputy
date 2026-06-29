"""China-mainland probe provider abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from typing import Any, Protocol

import requests


class ChinaProbeProvider(Protocol):
    def probe(self, proxy: dict, config: Any) -> Any: ...


@dataclass
class NoopChinaProbeProvider:
    """Default provider used until an external CN vantage source is configured."""

    name: str = "noop"

    def probe(self, proxy: dict, config: Any) -> Any:
        from deputy.probing.verification import ChinaProbeSummary

        return ChinaProbeSummary(
            source_provider=self.name,
            attempted_providers=[self.name],
        )


@dataclass
class ChainedChinaProbeProvider:
    """Try multiple providers in order until one returns non-empty samples."""

    providers: list[ChinaProbeProvider]
    name: str = "chain"

    def probe(self, proxy: dict, config: Any) -> Any:
        from deputy.probing.verification import ChinaProbeSummary

        attempted: list[str] = []
        for provider in self.providers:
            attempted.append(getattr(provider, "name", provider.__class__.__name__.lower()))
            summary = provider.probe(proxy, config)
            if getattr(summary, "sample_count", 0) > 0:
                return ChinaProbeSummary(
                    samples=summary.samples,
                    source_provider=getattr(summary, "source_provider", "") or getattr(provider, "name", ""),
                    attempted_providers=attempted,
                    sample_count=summary.sample_count,
                    success_count=summary.success_count,
                    timeout_count=summary.timeout_count,
                    reset_count=summary.reset_count,
                    refused_count=summary.refused_count,
                )
        return ChinaProbeSummary.empty().__class__(
            source_provider="",
            attempted_providers=attempted,
        )


@dataclass
class ItdogChinaProbeProvider:
    """Fetch CN TCP probe samples from ITDOG's public TCPing result page."""

    name: str = "itdog"
    base_url: str = "https://www.itdog.cn/tcping"

    def probe(self, proxy: dict, config: Any) -> Any:
        from deputy.probing.verification import ChinaProbeSummary

        server = str(proxy.get("server", "")).strip()
        port = str(proxy.get("port", "")).strip()
        if not server or not port:
            return ChinaProbeSummary.empty()

        timeout = max(int(getattr(config, "timeout", 5) or 5), 1)
        url = f"{self.base_url}/{server}:{port}"
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            response.raise_for_status()
        except requests.RequestException:
            return ChinaProbeSummary.empty()
        return self._parse_summary(response.text)

    def _parse_summary(self, html: str) -> Any:
        from deputy.probing.verification import ChinaProbeSample, ChinaProbeSummary

        samples: list[ChinaProbeSample] = []
        for attrs, row_html in re.findall(r'<tr class="node_tr"([^>]*)>(.*?)</tr>', html, flags=re.S):
            node_type = _extract_attr(attrs, "node_type")
            if node_type not in {"1", "2", "3"}:
                continue
            if _extract_attr(attrs, "offline") == "1":
                continue

            location = _extract_location(row_html)
            avg_text = _extract_cell_by_id_prefix(row_html, "avg_ping_")
            last_text = _extract_cell_by_id_prefix(row_html, "last_ping_")
            failure_reason = _normalize_failure_reason(f"{last_text} {avg_text}".strip())
            latency_ms = None if failure_reason else (_parse_latency(avg_text) or _parse_latency(last_text))
            ok = failure_reason is None and latency_ms is not None
            if not ok and failure_reason is None:
                failure_reason = "connect-failed"

            samples.append(
                ChinaProbeSample(
                    provider=self.name,
                    location=location,
                    ok=ok,
                    latency_ms=latency_ms,
                    failure_reason=None if ok else failure_reason,
                )
            )

        return ChinaProbeSummary(
            samples=samples,
            source_provider=self.name,
            attempted_providers=[self.name],
            sample_count=len(samples),
            success_count=sum(1 for sample in samples if sample.ok),
            timeout_count=sum(1 for sample in samples if sample.failure_reason == "timeout"),
            reset_count=sum(1 for sample in samples if sample.failure_reason == "connection-reset"),
            refused_count=sum(1 for sample in samples if sample.failure_reason == "connection-refused"),
        )


def get_china_probe_provider(name: str) -> ChinaProbeProvider:
    if name == "auto":
        return ChainedChinaProbeProvider(
            providers=[ItdogChinaProbeProvider(), NoopChinaProbeProvider()],
            name="auto",
        )
    if "," in name:
        providers = [_provider_from_token(token) for token in name.split(",") if token.strip()]
        return ChainedChinaProbeProvider(
            providers=providers or [NoopChinaProbeProvider()],
            name=name,
        )
    if name in {"", "noop", "none"}:
        return NoopChinaProbeProvider(name=name or "noop")
    if name == "itdog":
        return ItdogChinaProbeProvider()
    return NoopChinaProbeProvider(name=name)


def _provider_from_token(name: str) -> ChinaProbeProvider:
    token = name.strip().lower()
    if token in {"", "noop", "none"}:
        return NoopChinaProbeProvider(name=token or "noop")
    if token == "itdog":
        return ItdogChinaProbeProvider()
    return NoopChinaProbeProvider(name=token)


def _extract_attr(attrs: str, name: str) -> str:
    match = re.search(rf'{re.escape(name)}="([^"]*)"', attrs)
    return match.group(1) if match else ""


def _extract_location(row_html: str) -> str:
    cell_match = re.search(r'<td class="text-left"[^>]*>(.*?)</td>', row_html, flags=re.S)
    if not cell_match:
        return ""
    cell_html = cell_match.group(1)
    carrier_match = re.search(r"<span[^>]*>(.*?)</span>", cell_html, flags=re.S)
    carrier = _strip_tags(carrier_match.group(1)) if carrier_match else ""
    location_text = _strip_tags(cell_html)
    if carrier and location_text.startswith(carrier):
        location_text = location_text[len(carrier):].strip()
    return f"{location_text}{carrier}" if carrier and location_text else location_text


def _extract_cell_by_id_prefix(row_html: str, prefix: str) -> str:
    match = re.search(rf'<td[^>]*id="{re.escape(prefix)}[^"]*"[^>]*>(.*?)</td>', row_html, flags=re.S)
    return _strip_tags(match.group(1)) if match else ""


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = unescape(text).replace("\xa0", " ")
    return " ".join(text.split())


def _parse_latency(value: str) -> float | None:
    value = value.strip()
    if not value or value == "--":
        return None
    if value.startswith("<1"):
        return 0.5
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def _normalize_failure_reason(value: str) -> str | None:
    normalized = value.strip()
    lower = normalized.lower()
    if not normalized or normalized == "--":
        return None
    if "超时" in normalized or "timeout" in lower:
        return "timeout"
    if "拒绝" in normalized or "refused" in lower:
        return "connection-refused"
    if "重置" in normalized or "reset" in lower or "rst" in lower:
        return "connection-reset"
    return None

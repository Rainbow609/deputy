"""Tests for mainland probe providers."""

from __future__ import annotations

import requests

from deputy.probing.cn import (
    ChainedChinaProbeProvider,
    ChinaProbeProvider,
    ItdogChinaProbeProvider,
    get_china_probe_provider,
)
from deputy.probing.verification import ChinaProbeConfig


def _proxy() -> dict:
    return {"name": "node-1", "type": "vmess", "server": "1.2.3.4", "port": 443}


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None


def test_get_china_probe_provider_returns_itdog_provider():
    provider = get_china_probe_provider("itdog")
    assert isinstance(provider, ItdogChinaProbeProvider)


def test_get_china_probe_provider_supports_auto_and_chain_names():
    auto_provider = get_china_probe_provider("auto")
    assert isinstance(auto_provider, ChainedChinaProbeProvider)
    assert [provider.name for provider in auto_provider.providers] == ["itdog", "noop"]

    chained_provider = get_china_probe_provider("itdog,noop")
    assert isinstance(chained_provider, ChainedChinaProbeProvider)
    assert [provider.name for provider in chained_provider.providers] == ["itdog", "noop"]


def test_chained_provider_falls_back_when_previous_provider_returns_empty():
    class EmptyProvider:
        name = "empty"

        def probe(self, proxy: dict, config: ChinaProbeConfig):
            from deputy.probing.verification import ChinaProbeSummary

            return ChinaProbeSummary.empty()

    class SuccessProvider:
        name = "success"

        def probe(self, proxy: dict, config: ChinaProbeConfig):
            from deputy.probing.verification import ChinaProbeSample, ChinaProbeSummary

            return ChinaProbeSummary(
                samples=[ChinaProbeSample("success", "辽宁大连电信", True, 50.0, None)],
                sample_count=1,
                success_count=1,
                timeout_count=0,
                reset_count=0,
                refused_count=0,
            )

    provider = ChainedChinaProbeProvider([EmptyProvider(), SuccessProvider()])
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="empty,success", timeout=5))

    assert summary.sample_count == 1
    assert summary.success_count == 1
    assert summary.samples[0].provider == "success"
    assert summary.source_provider == "success"
    assert summary.attempted_providers == ["empty", "success"]


def test_chained_provider_stops_after_first_non_empty_provider():
    calls: list[str] = []

    class FirstProvider:
        name = "first"

        def probe(self, proxy: dict, config: ChinaProbeConfig):
            from deputy.probing.verification import ChinaProbeSample, ChinaProbeSummary

            calls.append("first")
            return ChinaProbeSummary(
                samples=[ChinaProbeSample("first", "江苏镇江电信", True, 40.0, None)],
                sample_count=1,
                success_count=1,
                timeout_count=0,
                reset_count=0,
                refused_count=0,
            )

    class SecondProvider:
        name = "second"

        def probe(self, proxy: dict, config: ChinaProbeConfig):
            calls.append("second")
            raise AssertionError("second provider should not run")

    provider = ChainedChinaProbeProvider([FirstProvider(), SecondProvider()])
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="first,second", timeout=5))

    assert summary.sample_count == 1
    assert calls == ["first"]
    assert summary.source_provider == "first"
    assert summary.attempted_providers == ["first"]


def test_chained_provider_keeps_attempt_trace_when_all_providers_return_empty():
    class EmptyProvider:
        name = "empty"

        def probe(self, proxy: dict, config: ChinaProbeConfig):
            from deputy.probing.verification import ChinaProbeSummary

            return ChinaProbeSummary.empty()

    provider = ChainedChinaProbeProvider([EmptyProvider(), EmptyProvider()])
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="empty,empty", timeout=5))

    assert summary.sample_count == 0
    assert summary.source_provider == ""
    assert summary.attempted_providers == ["empty", "empty"]


def test_itdog_provider_parses_mainland_rows_and_ignores_overseas(monkeypatch):
    html = """
    <table>
      <tbody>
        <tr class="node_tr" node="12" node_type="1" offline="0">
          <td class="text-left"><span class="badge badge-success">电信</span>辽宁大连</td>
          <td class="real_ip">1.2.3.4:443</td>
          <td class="ip_address">中国/香港/阿里云</td>
          <td id="loss_12">0%</td>
          <td id="send_12">100</td>
          <td id="last_ping_12">63</td>
          <td id="best_ping_12">47</td>
          <td id="worst_ping_12">125</td>
          <td id="avg_ping_12" class="table-avg">62</td>
        </tr>
        <tr class="node_tr" node="70" node_type="2" offline="0" time_out="true">
          <td class="text-left"><span class="badge badge-warning">联通</span>江苏宿迁</td>
          <td class="real_ip">1.2.3.4:443</td>
          <td class="ip_address">中国/香港/阿里云</td>
          <td id="loss_70">100%</td>
          <td id="send_70">100</td>
          <td id="last_ping_70"><span class="text-danger">超时</span></td>
          <td id="best_ping_70">--</td>
          <td id="worst_ping_70">--</td>
          <td id="avg_ping_70" class="table-avg">--</td>
        </tr>
        <tr class="node_tr" node="59" node_type="5" offline="0">
          <td class="text-left"><span class="badge badge-secondary">海外</span>中国香港</td>
          <td class="real_ip">1.2.3.4:443</td>
          <td class="ip_address">中国/香港/阿里云</td>
          <td id="loss_59">0%</td>
          <td id="send_59">100</td>
          <td id="last_ping_59">16</td>
          <td id="best_ping_59"><1</td>
          <td id="worst_ping_59">16</td>
          <td id="avg_ping_59" class="table-avg">4</td>
        </tr>
      </tbody>
    </table>
    """

    def fake_get(*args, **kwargs):
        return _FakeResponse(html)

    monkeypatch.setattr(requests, "get", fake_get)

    provider = ItdogChinaProbeProvider()
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="itdog", timeout=5))

    assert summary.sample_count == 2
    assert summary.success_count == 1
    assert summary.timeout_count == 1
    assert summary.refused_count == 0
    assert summary.source_provider == "itdog"
    assert summary.attempted_providers == ["itdog"]
    assert [sample.location for sample in summary.samples] == ["辽宁大连电信", "江苏宿迁联通"]
    assert summary.samples[0].latency_ms == 62.0
    assert summary.samples[1].failure_reason == "timeout"


def test_itdog_provider_normalizes_refused_and_reset(monkeypatch):
    html = """
    <table>
      <tbody>
        <tr class="node_tr" node="12" node_type="1" offline="0">
          <td class="text-left"><span class="badge badge-success">电信</span>辽宁大连</td>
          <td class="real_ip">1.2.3.4:443</td>
          <td class="ip_address">中国/香港/阿里云</td>
          <td id="loss_12">100%</td>
          <td id="send_12">100</td>
          <td id="last_ping_12"><span class="text-danger">连接被拒绝</span></td>
          <td id="best_ping_12">--</td>
          <td id="worst_ping_12">--</td>
          <td id="avg_ping_12" class="table-avg">--</td>
        </tr>
        <tr class="node_tr" node="72" node_type="3" offline="0">
          <td class="text-left"><span class="badge badge-info">移动</span>湖南长沙</td>
          <td class="real_ip">1.2.3.4:443</td>
          <td class="ip_address">中国/香港/阿里云</td>
          <td id="loss_72">100%</td>
          <td id="send_72">100</td>
          <td id="last_ping_72"><span class="text-danger">连接重置</span></td>
          <td id="best_ping_72">--</td>
          <td id="worst_ping_72">--</td>
          <td id="avg_ping_72" class="table-avg">--</td>
        </tr>
      </tbody>
    </table>
    """

    def fake_get(*args, **kwargs):
        return _FakeResponse(html)

    monkeypatch.setattr(requests, "get", fake_get)

    provider = ItdogChinaProbeProvider()
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="itdog", timeout=5))

    assert summary.sample_count == 2
    assert summary.success_count == 0
    assert summary.timeout_count == 0
    assert summary.refused_count == 1
    assert summary.reset_count == 1
    assert [sample.failure_reason for sample in summary.samples] == [
        "connection-refused",
        "connection-reset",
    ]


def test_itdog_provider_returns_empty_on_request_failure(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(requests, "get", fake_get)

    provider = ItdogChinaProbeProvider()
    summary = provider.probe(_proxy(), ChinaProbeConfig(enabled=True, provider="itdog", timeout=5))

    assert summary.sample_count == 0
    assert summary.success_count == 0

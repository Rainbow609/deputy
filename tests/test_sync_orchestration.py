"""Tests for the run_sync orchestration entry point."""

from __future__ import annotations

import io
import socket
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from deputy.core.sync import _should_emit_ci_artifacts, run_sync
from deputy.sources.subscription import SubscriptionFetchResult
from deputy.transport.chain import TransportError
from deputy.utils.logging import GhaLogger


MOCK_CLASH = """
proxies:
  - {name: "mock-hk-1", type: vmess, server: 1.1.1.1, port: 443, uuid: u, alterId: 0, cipher: auto}
  - {name: "mock-sg-1", type: ss, server: 2.2.2.2, port: 8388, cipher: aes-256-gcm, password: p}
"""


def _write_basic_config(path: Path, **extras) -> None:
    body = """
[subscription]
format = "clash"
exclude_keywords = []

[probe]
timeout = 1
concurrency = 4
retries = 0
address_family = "auto"

[subscription_sources]
mock = "https://mock.example.com/sub"
"""
    body += "\n".join(f"{k} = {v!r}" for k, v in extras.items()) + "\n"
    path.write_text(body, encoding="utf-8")


def _mock_socket_success():
    class FakeSocket:
        def __init__(self, *args, **kwargs):
            pass

        def connect_ex(self, sockaddr):
            return 0

        def setsockopt(self, *a, **kw):
            return None

        def settimeout(self, *a, **kw):
            return None

        def close(self):
            return None

    return FakeSocket


def test_run_sync_happy_path_writes_config(tmp_path: Path):
    cfg = tmp_path / "sync_config.toml"
    _write_basic_config(cfg)
    template = tmp_path / "config.template.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}{SUB_PROXIES}\n", encoding="utf-8"
    )
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(sub_url, prefix, cache_dir, fetch_cfg, transport_chain):
        return SubscriptionFetchResult(
            source=prefix,
            proxies=[{"name": "mock-hk-1", "type": "vmess", "server": "1.1.1.1",
                      "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
            status="fresh",
            cache_status="updated",
        )

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    fake_socket_factory = _mock_socket_success()
    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with patch("deputy.probing.tcp.socket.socket", side_effect=fake_socket_factory):
            with patch("deputy.probing.tcp.socket.getaddrinfo",
                       return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
                summary = run_sync(
                    config_path=cfg,
                    template_path=template,
                    output_config=output,
                    previous_config=previous,
                    logger=logger,
                )

    assert output.exists()
    rendered = output.read_text(encoding="utf-8")
    assert "mock-hk-1" in rendered
    assert summary["alive"] >= 1
    assert summary["version"].startswith("v")


def test_run_sync_fails_when_all_sources_fail(tmp_path: Path):
    cfg = tmp_path / "sync_config.toml"
    _write_basic_config(cfg)
    template = tmp_path / "config.template.yaml"
    template.write_text("proxies: []\n", encoding="utf-8")
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(*a, **kw):
        raise TransportError("bad upstream")

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with pytest.raises(RuntimeError):
            run_sync(
                config_path=cfg,
                template_path=template,
                output_config=output,
                previous_config=previous,
                logger=logger,
            )
    # Output should NOT have been written when no alive nodes exist.
    assert not output.exists()


def test_run_sync_fails_when_zero_alive(tmp_path: Path):
    cfg = tmp_path / "sync_config.toml"
    _write_basic_config(cfg)
    template = tmp_path / "config.template.yaml"
    template.write_text("proxies: []\n", encoding="utf-8")
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(sub_url, prefix, cache_dir, fetch_cfg, transport_chain):
        return SubscriptionFetchResult(
            source=prefix,
            proxies=[{"name": "dead-1", "type": "vmess", "server": "2.2.2.2",
                      "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"}],
            status="fresh",
            cache_status="updated",
        )

    fake_socket_factory = lambda *a, **kw: type(
        "S", (), {"connect_ex": lambda s: 1, "close": lambda s: None}
    )()
    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with patch("deputy.probing.tcp.socket.socket", side_effect=fake_socket_factory):
            with patch("deputy.probing.tcp.socket.getaddrinfo",
                       return_value=[(2, 1, 6, "", ("2.2.2.2", 443))]):
                with pytest.raises(RuntimeError, match="zero alive"):
                    run_sync(
                        config_path=cfg,
                        template_path=template,
                        output_config=output,
                        previous_config=previous,
                        logger=logger,
                    )
    assert not output.exists()


def test_run_sync_applies_verification_policy_and_emits_summary(tmp_path: Path):
    cfg = tmp_path / "sync_config.toml"
    cfg.write_text(
        """
[subscription]
format = "clash"
exclude_keywords = []

[probe]
timeout = 1
concurrency = 4
retries = 0
address_family = "auto"

[probe.classifier]
filter_mode = "exclude_confirmed"
history_path = "history.json"

[subscription_sources]
mock = "https://mock.example.com/sub"
""",
        encoding="utf-8",
    )
    template = tmp_path / "config.template.yaml"
    template.write_text("proxies:\n{LOCAL_PROXIES}{SUB_PROXIES}\n", encoding="utf-8")
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(sub_url, prefix, cache_dir, fetch_cfg, transport_chain):
        return SubscriptionFetchResult(
            source=prefix,
            proxies=[
                {"name": "ok-1", "type": "vmess", "server": "1.1.1.1", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
                {"name": "blocked-1", "type": "vmess", "server": "2.2.2.2", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
            ],
            status="fresh",
            cache_status="updated",
        )

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    fake_probe_result = type(
        "ProbeResult",
        (),
        {
            "alive": [
                {"name": "ok-1", "type": "vmess", "server": "1.1.1.1", "port": 443},
                {"name": "blocked-1", "type": "vmess", "server": "2.2.2.2", "port": 443},
            ],
            "dead": [],
            "stats_by_name": {
                "ok-1": {"avg_ms": 50.0},
                "blocked-1": {"avg_ms": 70.0},
            },
        },
    )()

    def fake_assess_nodes(*args, **kwargs):
        return {
            "vmess|1.1.1.1|443": {
                "status": "reachable",
                "block_confidence": 0,
                "policy_action": "keep",
                "reasons": ["cn-tcp-ok"],
                "signal_summary": {
                    "cn_tcp": {
                        "sample_count": 3,
                        "success_count": 2,
                        "timeout_count": 1,
                        "reset_count": 0,
                        "refused_count": 0,
                        "samples": [{"provider": "itdog", "location": "辽宁大连电信", "ok": True}],
                    },
                    "mihomo_delay": {"ok": True, "delay_ms": 111},
                },
            },
            "vmess|2.2.2.2|443": {
                "status": "blocked_confirmed",
                "block_confidence": 90,
                "policy_action": "exclude",
                "reasons": ["cn-tcp-all-failed"],
                "signal_summary": {
                    "cn_tcp": {
                        "sample_count": 3,
                        "success_count": 0,
                        "timeout_count": 2,
                        "reset_count": 1,
                        "refused_count": 0,
                        "samples": [{"provider": "itdog", "location": "江苏宿迁联通", "ok": False}],
                    },
                    "mihomo_delay": {"ok": False, "delay_ms": None, "failure_reason": "timeout"},
                },
            },
        }

    with patch("deputy.core.sync.fetch_subscription_with_cache", side_effect=fake_fetch_with_cache):
        with patch("deputy.core.sync.tcp_probe", return_value=fake_probe_result):
            with patch("deputy.core.sync.assess_nodes", side_effect=fake_assess_nodes):
                summary = run_sync(
                    config_path=cfg,
                    template_path=template,
                    output_config=output,
                    previous_config=previous,
                    logger=logger,
                )

    rendered = output.read_text(encoding="utf-8")
    assert "ok-1" in rendered
    assert "blocked-1" not in rendered
    assert summary["policy_counts"] == Counter({"keep": 1, "exclude": 1})
    assert summary["status_counts"]["blocked_confirmed"] == 1
    assert summary["verification_overview"]["cn_provider"] == "itdog"
    assert summary["verification_overview"]["cn_sample_count"] == 6
    assert summary["mihomo_overview"]["tested_nodes"] == 2
    assert summary["mihomo_overview"]["success_count"] == 1
    assert summary["mihomo_overview"]["failure_count"] == 1
    assert summary["mihomo_overview"]["timeout_count"] == 1
    assert summary["mihomo_overview"]["success_rate"] == 50.0


def test_should_emit_ci_artifacts_respects_bootstrap_opt_out(monkeypatch):
    monkeypatch.delenv("DEPUTY_SKIP_CI_ARTIFACTS", raising=False)
    assert _should_emit_ci_artifacts() is True

    monkeypatch.setenv("DEPUTY_SKIP_CI_ARTIFACTS", "1")
    assert _should_emit_ci_artifacts() is False

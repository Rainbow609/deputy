"""End-to-end smoke test using a mocked subscription source.

Mirrors the legacy ``test_e2e_smoke.py`` with patch paths migrated from
``scripts.*`` to ``deputy.*``.
"""

from __future__ import annotations

import io
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

from deputy.core.sync import run_sync
from deputy.sources.subscription import SubscriptionFetchResult
from deputy.transport.chain import TransportError
from deputy.utils.logging import GhaLogger


MOCK_CLASH = """
proxies:
  - {name: "mock-hk-1", type: vmess, server: 1.1.1.1, port: 443, uuid: u, alterId: 0, cipher: auto}
  - {name: "mock-sg-1", type: ss, server: 2.2.2.2, port: 8388, cipher: aes-256-gcm, password: p}
"""


def _basic_config(tmp_path: Path, name: str = "sync_config.toml") -> Path:
    config_toml = tmp_path / name
    config_toml.write_text(
        """
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
""",
        encoding="utf-8",
    )
    return config_toml


def _fake_socket_factory():
    class FakeSocket:
        def __init__(self, *args, **kwargs):
            self._ok = True

        def connect_ex(self, sockaddr):
            return 0

        def setsockopt(self, *a, **kw):
            return None

        def settimeout(self, *a, **kw):
            return None

        def close(self):
            return None

    return FakeSocket


def test_e2e_runs_pipeline_and_writes_config(tmp_path: Path):
    config_toml = _basic_config(tmp_path)
    template = tmp_path / "config.template.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\ngroups:\n  - {DIALER_LIST}\n",
        encoding="utf-8",
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

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with patch("deputy.probing.tcp.socket.socket", side_effect=_fake_socket_factory()):
            with patch("deputy.probing.tcp.socket.getaddrinfo",
                       return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
                summary = run_sync(
                    config_path=config_toml,
                    template_path=template,
                    output_config=output,
                    previous_config=previous,
                    logger=logger,
                )

    assert output.exists()
    rendered = output.read_text(encoding="utf-8")
    assert len(rendered) > 0
    assert summary["alive"] >= 1
    assert summary["version"].startswith("v")


def test_e2e_does_not_publish_when_all_sources_fail(tmp_path: Path):
    config_toml = _basic_config(tmp_path)
    template = tmp_path / "config.template.yaml"
    template.write_text("proxies:\n{LOCAL_PROXIES}{SUB_PROXIES}\n", encoding="utf-8")
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(*a, **kw):
        raise TransportError("bad upstream")

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        try:
            run_sync(
                config_path=config_toml,
                template_path=template,
                output_config=output,
                previous_config=previous,
                logger=logger,
            )
        except RuntimeError as exc:
            # E2E smoke asserts all-fail raise even when cache exists.
            assert "all subscription sources failed" in str(exc) or "zero alive" in str(exc)
        else:
            raise AssertionError("run_sync should fail when all sources fail")

    assert not output.exists()


def test_e2e_rename_applies_prefix_and_sanitizes(tmp_path: Path):
    config_toml = tmp_path / "sync_config.toml"
    config_toml.write_text(
        """
[subscription]
format = "clash"
exclude_keywords = ["⚡"]

[probe]
timeout = 1
concurrency = 4
retries = 0
address_family = "auto"

[subscription_sources]
mock = "https://mock.example.com/sub"

[rename]
sanitize = true

[rename.mock]
prefix = "MK"
""",
        encoding="utf-8",
    )
    template = tmp_path / "config.template.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\n", encoding="utf-8"
    )
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(sub_url, prefix, cache_dir, fetch_cfg, transport_chain):
        # Already-prefixed proxies (transport chain already applied prefix).
        return SubscriptionFetchResult(
            source=prefix,
            proxies=[
                {"name": "MK-HK01", "type": "vmess", "server": "1.1.1.1",
                 "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
            ],
            status="fresh",
            cache_status="updated",
        )

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with patch("deputy.probing.tcp.socket.socket", side_effect=_fake_socket_factory()):
            with patch("deputy.probing.tcp.socket.getaddrinfo",
                       return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
                summary = run_sync(
                    config_path=config_toml,
                    template_path=template,
                    output_config=output,
                    previous_config=previous,
                    logger=logger,
                )

    assert output.exists()
    rendered = output.read_text(encoding="utf-8")
    assert "MK-HK01" in rendered
    assert summary["alive"] >= 1


def test_e2e_does_not_publish_when_no_nodes_survive_verification(tmp_path: Path):
    config_toml = _basic_config(tmp_path)
    template = tmp_path / "config.template.yaml"
    template.write_text("{PROXIES_BLOCK}", encoding="utf-8")
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

    class FailingSocket:
        def __init__(self):
            pass

        def connect_ex(self, sockaddr):
            return 1

        def setsockopt(self, *a, **kw):
            return None

        def settimeout(self, *a, **kw):
            return None

        def close(self):
            return None

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache",
               side_effect=fake_fetch_with_cache):
        with patch("deputy.probing.tcp.socket.socket", side_effect=FailingSocket):
            with patch("deputy.probing.tcp.socket.getaddrinfo",
                       return_value=[(2, 1, 6, "", ("2.2.2.2", 443))]):
                try:
                    run_sync(
                        config_path=config_toml,
                        template_path=template,
                        output_config=output,
                        previous_config=previous,
                        logger=logger,
                    )
                except RuntimeError as exc:
                    assert "zero alive" in str(exc)
                else:
                    raise AssertionError("run_sync should fail before publishing an empty config")

    assert not output.exists()


def test_e2e_history_promotes_suspected_to_confirmed_and_filters(tmp_path: Path):
    config_toml = tmp_path / "sync_config.toml"
    config_toml.write_text(
        """
[subscription]
format = "clash"
exclude_keywords = []

[probe]
timeout = 1
concurrency = 4
retries = 0
address_family = "auto"

[probe.cn]
enabled = true
provider = "mock"
min_vantages = 3
min_success_vantages = 2
timeout = 5
stale_after_seconds = 600

[probe.health]
enabled = true
kind = "mihomo_delay"
controller_url = "http://127.0.0.1:9093"
secret = ""
test_url = "https://www.gstatic.com/generate_204"
timeout_ms = 10000
expected = "200,204"

[probe.classifier]
confirm_after_runs = 2
filter_mode = "exclude_confirmed"
history_path = "artifacts/verification-history.json"

[subscription_sources]
mock = "https://mock.example.com/sub"
""",
        encoding="utf-8",
    )
    template = tmp_path / "config.template.yaml"
    template.write_text("proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\n", encoding="utf-8")
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    def fake_fetch_with_cache(sub_url, prefix, cache_dir, fetch_cfg, transport_chain):
        return SubscriptionFetchResult(
            source=prefix,
            proxies=[
                {"name": "healthy-1", "type": "vmess", "server": "1.1.1.1", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
                {"name": "blocked-1", "type": "vmess", "server": "2.2.2.2", "port": 443, "uuid": "u", "alterId": 0, "cipher": "auto"},
            ],
            status="fresh",
            cache_status="updated",
        )

    class FakeCnProvider:
        def probe(self, proxy, config):
            from deputy.probing.verification import ChinaProbeSample, ChinaProbeSummary

            if proxy["server"] == "1.1.1.1":
                return ChinaProbeSummary(
                    samples=[
                        ChinaProbeSample("mock", "cn-1", True, 50.0, None),
                        ChinaProbeSample("mock", "cn-2", True, 55.0, None),
                        ChinaProbeSample("mock", "cn-3", False, None, "timeout"),
                    ],
                    sample_count=3,
                    success_count=2,
                    timeout_count=1,
                    reset_count=0,
                    refused_count=0,
                )
            return ChinaProbeSummary(
                samples=[
                    ChinaProbeSample("mock", "cn-1", False, None, "timeout"),
                    ChinaProbeSample("mock", "cn-2", False, None, "timeout"),
                    ChinaProbeSample("mock", "cn-3", False, None, "connection-refused"),
                ],
                sample_count=3,
                success_count=0,
                timeout_count=2,
                reset_count=0,
                refused_count=1,
            )

    class FakeProbeResult:
        alive = [
            {"name": "healthy-1", "type": "vmess", "server": "1.1.1.1", "port": 443},
            {"name": "blocked-1", "type": "vmess", "server": "2.2.2.2", "port": 443},
        ]
        dead = []
        stats_by_name = {
            "healthy-1": {"avg_ms": 50.0},
            "blocked-1": {"avg_ms": 80.0},
        }

    def fake_health_check(self, proxy, config):
        from deputy.probing.health import HealthCheckResult

        if proxy["server"] == "1.1.1.1":
            return HealthCheckResult(ok=True, delay_ms=120)
        return HealthCheckResult(ok=False, failure_reason="timeout")

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("deputy.core.sync.fetch_subscription_with_cache", side_effect=fake_fetch_with_cache):
        with patch("deputy.core.sync.tcp_probe", return_value=FakeProbeResult()):
            with patch("deputy.core.sync.get_china_probe_provider", return_value=FakeCnProvider()):
                with patch("deputy.core.sync.MihomoDelayChecker.check", new=fake_health_check):
                    first = run_sync(
                        config_path=config_toml,
                        template_path=template,
                        output_config=output,
                        previous_config=previous,
                        logger=logger,
                    )
                    first_rendered = output.read_text(encoding="utf-8")

                    second = run_sync(
                        config_path=config_toml,
                        template_path=template,
                        output_config=output,
                        previous_config=previous,
                        logger=logger,
                    )
                    second_rendered = output.read_text(encoding="utf-8")

    assert "blocked-1" in first_rendered
    assert "healthy-1" in first_rendered
    assert first["status_counts"]["suspected_gfw_blocked"] == 1
    assert first["status_counts"]["reachable"] == 1
    assert "blocked-1" not in second_rendered
    assert "healthy-1" in second_rendered
    assert second["status_counts"]["blocked_confirmed"] == 1
    assert second["status_counts"]["reachable"] == 1
    assert second["policy_counts"]["exclude"] == 1


def test_actions_workflow_runs_two_pass_mihomo_health_path():
    workflow = Path(".github/workflows/sync-and-release.yml").read_text(encoding="utf-8")

    assert "Run bootstrap sync" in workflow
    assert "Download Mihomo" in workflow
    assert "Start Mihomo controller" in workflow
    assert "Prepare verification-enabled config" in workflow
    assert 's/(\\[probe\\.cn\\]\\s*enabled\\s*=\\s*)false/${1}true/s' in workflow
    assert 's/(provider\\s*=\\s*)"noop"/${1}"auto"/s' in workflow
    assert "Run sync with CN probe and Mihomo health" in workflow
    assert "sync_config.health.toml" in workflow
    assert "http://127.0.0.1:9093/version" in workflow
    assert "Authorization: Bearer deputy-ci" in workflow

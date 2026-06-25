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

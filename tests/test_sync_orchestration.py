"""Tests for the run_sync orchestration entry point."""

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

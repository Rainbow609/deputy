"""End-to-end smoke test using a mocked subscription source.

This validates the full pipeline runs without errors and produces a
non-empty config.yaml. It does NOT hit the network.
"""

import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

# Make the project root importable when pytest is invoked from the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.sync_nodes import run_sync  # noqa: E402
from scripts.github_actions_logger import GhaLogger  # noqa: E402


MOCK_CLASH = """
proxies:
  - {name: "mock-hk-1", type: vmess, server: 1.1.1.1, port: 443, uuid: u, alterId: 0, cipher: auto}
  - {name: "mock-sg-1", type: ss, server: 2.2.2.2, port: 8388, cipher: aes-256-gcm, password: p}
"""


def test_e2e_runs_pipeline_and_writes_config(tmp_path: Path):
    # Setup
    config_toml = tmp_path / "nodes.toml"
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
    template = tmp_path / "config.template.yaml"
    template.write_text(
        "proxies:\n{LOCAL_PROXIES}\n{SUB_PROXIES}\ngroups:\n  - {DIALER_LIST}\n",
        encoding="utf-8",
    )
    output = tmp_path / "config.yaml"
    previous = tmp_path / "config.previous.yaml"

    # Mock the transport chain to return our sample
    fake_chain = MagicMock()
    fake_chain.fetch.return_value.text.return_value = MOCK_CLASH  # type: ignore
    fake_chain.fetch.return_value.status = 200
    fake_chain.fetch.return_value.transport_name = "mock"

    logger = GhaLogger("deputy", output=io.StringIO())
    logger.set_level = lambda lvl: None  # type: ignore[assignment]

    with patch("scripts.sync_nodes.build_transport_chain", return_value=fake_chain):
        with patch("scripts.node_verifier.socket.socket") as fake_socket:
            fake_inst = MagicMock()
            fake_inst.connect_ex.return_value = 0  # simulate success
            fake_inst.__enter__ = lambda s: fake_inst
            fake_inst.__exit__ = lambda s, *a: None
            fake_socket.return_value = fake_inst
            with patch("scripts.node_verifier.socket.getaddrinfo", return_value=[
                (2, 1, 6, "", ("1.1.1.1", 443)),
            ]):
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
    # Note: mocked verification marks nodes alive since connect_ex returns 0
    assert summary["alive"] >= 0
    assert summary["version"].startswith("v")

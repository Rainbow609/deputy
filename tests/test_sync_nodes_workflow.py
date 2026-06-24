"""Tests for the published GitHub Actions workflow YAML."""

from __future__ import annotations

from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sync-and-release.yml"


def test_workflow_yaml_parses():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert data["name"] == "Sync Nodes and Release"


def test_workflow_triggers_include_schedule_and_dispatch():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    triggers = data[True]  # YAML uses `True` as the on: key
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers


def test_workflow_push_paths_include_src_deputy():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    paths = data[True]["push"]["paths"]
    assert "src/deputy/**" in paths
    assert "scripts/sync_nodes.py" in paths
    assert "sync_config.toml" in paths
    # No more nodes.toml
    assert "nodes.toml" not in paths


def test_workflow_run_sync_uses_new_entry_point():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    sync_step = next(
        s for s in data["jobs"]["sync"]["steps"] if s.get("name") == "Run sync"
    )
    cmd = sync_step["run"]
    assert "scripts/sync_nodes.py" in cmd
    assert "sync_config.toml" in cmd


def test_workflow_keeps_github_releases_step():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    release_step = next(
        s for s in data["jobs"]["sync"]["steps"]
        if s.get("uses", "").startswith("softprops/action-gh-release")
    )
    with_block = release_step["with"]
    assert with_block["tag_name"] == "deputy-latest"
    assert "config.yaml" in with_block["files"]
    assert with_block["fail_on_unmatched_files"] is False


def test_workflow_release_step_guarded_by_hashfiles():
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    release_step = next(
        s for s in data["jobs"]["sync"]["steps"]
        if s.get("uses", "").startswith("softprops/action-gh-release")
    )
    assert "hashFiles" in release_step.get("if", "")


def test_workflow_does_not_introduce_gist_or_config_output():
    """Per design decision: do not migrate to mihomo-config's Gist / config-output."""
    text = WORKFLOW_PATH.read_text()
    assert "gist" not in text.lower()
    assert "config-output" not in text

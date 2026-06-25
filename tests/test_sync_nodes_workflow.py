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


def test_workflow_has_cache_restore_step():
    """Ensure the workflow restores subscription caches before running sync."""
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    steps = data["jobs"]["sync"]["steps"]

    run_sync_idx = next(
        i for i, s in enumerate(steps) if s.get("name") == "Run sync"
    )

    cache_restore_steps = [
        s for s in steps[:run_sync_idx] if s.get("name") == "Restore subscription caches"
    ]
    assert len(cache_restore_steps) == 1, "Missing cache restore step before Run sync"

    cache_step = cache_restore_steps[0]
    assert cache_step["uses"].startswith("actions/cache/restore"), "Cache restore should use actions/cache/restore"
    assert cache_step["with"]["path"] == "subscriptions/", "Cache path should be subscriptions/"
    assert "key" in cache_step["with"], "Cache step should have key"
    assert "restore-keys" in cache_step["with"], "Cache restore step should have restore-keys"


def test_workflow_has_cache_save_step():
    """Ensure the workflow saves subscription caches after running sync."""
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    steps = data["jobs"]["sync"]["steps"]

    run_sync_idx = next(
        i for i, s in enumerate(steps) if s.get("name") == "Run sync"
    )

    cache_save_steps = [
        s for s in steps[run_sync_idx + 1 :] if s.get("name") == "Save subscription caches"
    ]
    assert len(cache_save_steps) == 1, "Missing cache save step after Run sync"

    cache_step = cache_save_steps[0]
    assert cache_step["uses"].startswith("actions/cache/save"), "Cache save should use actions/cache/save"
    assert cache_step.get("if") == "always()", "Cache save should run even if sync fails"
    assert cache_step["with"]["path"] == "subscriptions/", "Cache path should be subscriptions/"
    assert "key" in cache_step["with"], "Cache step should have key"


def test_workflow_does_not_introduce_gist_or_config_output():
    """Per design decision: do not migrate to mihomo-config's Gist / config-output."""
    text = WORKFLOW_PATH.read_text()
    assert "gist" not in text.lower()
    assert "config-output" not in text


def test_workflow_uses_node24_compatible_actions():
    """Ensure actions use Node 24 compatible versions to avoid deprecation warnings.

    References:
    - actions/cache v5: https://github.com/actions/cache (updated to node 24)
    - actions/checkout v7: https://github.com/actions/checkout (ESM, node 24)
    - setup-uv v8.2.0: https://github.com/astral-sh/setup-uv (immutable release)
    """
    text = WORKFLOW_PATH.read_text()
    # actions/cache v4 uses Node 20 which is deprecated as of June 2026
    assert "actions/cache/restore@v4" not in text, "Upgrade to actions/cache/restore@v5 for Node 24"
    assert "actions/cache/save@v4" not in text, "Upgrade to actions/cache/save@v5 for Node 24"
    assert "actions/cache/restore@v5" in text, "Use actions/cache/restore@v5 (Node 24)"
    assert "actions/cache/save@v5" in text, "Use actions/cache/save@v5 (Node 24)"

    # astral-sh/setup-uv v7 may use Node 20; v8+ uses immutable releases
    assert "astral-sh/setup-uv@v7" not in text, "Upgrade to setup-uv@v8.2.0+ for Node 24"
    assert "astral-sh/setup-uv@v8.2.0" in text, "Use setup-uv@v8.2.0 (immutable, Node 24)"

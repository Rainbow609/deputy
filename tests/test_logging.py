"""Tests for the structured logger and step-summary builder."""

from __future__ import annotations

import io
import os

import pytest

from deputy.utils.logging import (
    GhaLogger,
    LogLevel,
    StepSummaryBuilder,
    is_ci,
    utc_now_iso,
)


def test_logger_emits_json_for_info(capsys):
    out = io.StringIO()
    log = GhaLogger("deputy", output=out)
    log.info("hello", {"x": 1})
    line = out.getvalue().strip()
    import json as _json

    payload = _json.loads(line)
    assert payload["msg"] == "hello"
    assert payload["fields"] == {"x": 1}
    assert payload["level"] == "INFO"


def test_logger_error_writes_to_separate_field(capsys):
    out = io.StringIO()
    log = GhaLogger("deputy", output=out, is_github_actions=True)
    log.error("boom")
    # GhaLogger writes "::error::boom\n" then optionally a JSON line
    assert "::error::boom" in out.getvalue()


def test_logger_group_emits_github_workflow_commands():
    out = io.StringIO()
    log = GhaLogger("deputy", output=out, is_github_actions=True)
    with log.group("phase"):
        log.info("inside")
    output = out.getvalue()
    assert "::group::phase" in output
    assert "::endgroup::" in output


def test_logger_set_level_filters_debug():
    out = io.StringIO()
    log = GhaLogger("deputy", output=out)
    log.set_level(LogLevel.WARNING)
    log.debug("hidden")
    assert out.getvalue() == ""


def test_is_ci_returns_bool():
    assert isinstance(is_ci(), bool)


def test_utc_now_iso_is_z_suffix():
    s = utc_now_iso()
    assert s.endswith("Z")
    assert "T" in s


def test_step_summary_builder_writes_table(monkeypatch, tmp_path):
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    sb = StepSummaryBuilder()
    sb.heading("Results", level=2)
    sb.table(["A", "B"], [("1", "2"), ("3", "4")])
    sb.write()
    text = summary_file.read_text()
    assert "## Results" in text
    assert "| A | B |" in text
    assert "| 1 | 2 |" in text
    assert "| 3 | 4 |" in text


def test_step_summary_builder_json_block(monkeypatch, tmp_path):
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    sb = StepSummaryBuilder()
    sb.json_block({"alive": 3, "total": 5})
    sb.write()
    text = summary_file.read_text()
    assert "```json" in text
    assert '"alive": 3' in text

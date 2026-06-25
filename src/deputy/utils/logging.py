"""GitHub Actions-friendly structured logger and step-summary builder.

Combines deputy's original ``GhaLogger`` (preserving the dataclass-based
structured logging) with mihomo-config-style workflow command helpers
(``is_ci`` / ``warning`` / ``error`` / ``set_output`` / ``add_mask`` / …)
and a chainable ``StepSummaryBuilder`` that writes to ``$GITHUB_STEP_SUMMARY``.
"""

from __future__ import annotations

import enum
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import IO, Any


class LogLevel(enum.IntEnum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass
class GhaLogger:
    """Structured JSON logger that emits ``::group::`` / ``::error::`` in CI."""

    name: str
    output: IO[str] = sys.stdout
    is_github_actions: bool = field(
        default_factory=lambda: os.environ.get("GITHUB_ACTIONS") == "true"
    )
    _level: LogLevel = LogLevel.INFO

    def set_level(self, level: LogLevel) -> None:
        self._level = level

    def _format(self, level: LogLevel, msg: str, fields: dict[str, Any] | None) -> str:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload: dict[str, Any] = {"ts": ts, "level": level.name, "logger": self.name, "msg": msg}
        if fields:
            payload["fields"] = fields
        return json.dumps(payload, ensure_ascii=False)

    def _emit(self, level: LogLevel, msg: str, fields: dict[str, Any] | None) -> None:
        if level < self._level:
            return
        if level == LogLevel.ERROR and self.is_github_actions:
            self.output.write(f"::error::{msg}\n")
            if fields:
                self.output.write(self._format(level, msg, fields) + "\n")
            self.output.flush()
            return
        self.output.write(self._format(level, msg, fields) + "\n")
        self.output.flush()

    def debug(self, msg: str, fields: dict[str, Any] | None = None) -> None:
        self._emit(LogLevel.DEBUG, msg, fields)

    def info(self, msg: str, fields: dict[str, Any] | None = None) -> None:
        self._emit(LogLevel.INFO, msg, fields)

    def warning(self, msg: str, fields: dict[str, Any] | None = None) -> None:
        self._emit(LogLevel.WARNING, msg, fields)

    def error(self, msg: str, fields: dict[str, Any] | None = None) -> None:
        self._emit(LogLevel.ERROR, msg, fields)

    @contextmanager
    def group(self, title: str):
        if self.is_github_actions:
            self.output.write(f"::group::{title}\n")
            self.output.flush()
        try:
            yield self
        finally:
            if self.is_github_actions:
                self.output.write("::endgroup::\n")
                self.output.flush()


# ── Module-level workflow-command helpers (mihomo-config style) ────────────


def is_ci() -> bool:
    """Return True when running inside GitHub Actions."""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _command(level: str, message: str, **params) -> str:
    parts = [f"::{level}"]
    for key in ("file", "line", "col", "endLine", "endColumn", "title"):
        value = params.get(key)
        if value is not None:
            value = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            parts.append(f"{key}={value}")
    parts.append(f"::{message}")
    return " ".join(parts)


def debug(message: str) -> None:
    if is_ci():
        print(_command("debug", message), file=sys.stderr)
    else:
        print(f"[DEBUG] {message}", file=sys.stderr)


def notice(message: str, **kwargs) -> None:
    if is_ci():
        print(_command("notice", message, **kwargs), file=sys.stderr)
    else:
        print(f"[NOTICE] {message}", file=sys.stderr)


def warning(message: str, **kwargs) -> None:
    if is_ci():
        print(_command("warning", message, **kwargs), file=sys.stderr)
    else:
        print(f"[WARNING] {message}", file=sys.stderr)


def error(message: str, **kwargs) -> None:
    if is_ci():
        print(_command("error", message, **kwargs), file=sys.stderr)
    else:
        print(f"[ERROR] {message}", file=sys.stderr)


def group(name: str) -> None:
    if is_ci():
        print(f"::group::{name}")
    else:
        print(f"\n=== {name} ===")


def endgroup() -> None:
    if is_ci():
        print("::endgroup::")
    else:
        print("=== end ===\n")


def set_output(name: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    elif is_ci():
        print(f"::set-output name={name}::{value}")


def set_env(name: str, value: str) -> None:
    env_file = os.environ.get("GITHUB_ENV")
    if env_file:
        with open(env_file, "a") as f:
            f.write(f"{name}={value}\n")


def add_mask(value: str) -> None:
    if is_ci():
        print(f"::add-mask::{value}")


def write_summary(markdown: str) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(markdown)
    elif is_ci():
        print("Warning: GITHUB_STEP_SUMMARY not set", file=sys.stderr)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ── Step summary builder ────────────────────────────────────────────────────


class StepSummaryBuilder:
    """Build a GitHub Actions step summary incrementally."""

    def __init__(self):
        self._lines: list[str] = []

    def heading(self, text: str, level: int = 2) -> "StepSummaryBuilder":
        self._lines.append(f"{'#' * level} {text}\n")
        return self

    def paragraph(self, text: str) -> "StepSummaryBuilder":
        self._lines.append(f"{text}\n")
        return self

    def table(self, headers, rows) -> "StepSummaryBuilder":
        self._lines.append("| " + " | ".join(headers) + " |\n")
        self._lines.append("| " + " | ".join(["---"] * len(headers)) + " |\n")
        for row in rows:
            self._lines.append("| " + " | ".join(str(c) for c in row) + " |\n")
        self._lines.append("\n")
        return self

    def code_block(self, text: str, language: str = "") -> "StepSummaryBuilder":
        self._lines.append(f"```{language}\n{text}\n```\n")
        return self

    def json_block(self, data: Any) -> "StepSummaryBuilder":
        return self.code_block(json.dumps(data, ensure_ascii=False, indent=2), language="json")

    def finalize(self) -> str:
        self._lines.append(f"\n*Run completed at {utc_now_iso()}*\n")
        return "".join(self._lines)

    def write(self) -> None:
        write_summary(self.finalize())

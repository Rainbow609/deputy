"""GitHub Actions-friendly structured logger.

Outputs GitHub workflow commands (::group::, ::error::) when running in
GitHub Actions, plain structured JSON-style lines otherwise. Designed to
minimize noise in workflow logs while still surfacing failures loudly.
"""

from __future__ import annotations

import enum
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, IO


class LogLevel(enum.IntEnum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass
class GhaLogger:
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
"""GitHub Releases publisher.

The publisher is conditional: it only creates a release when the rendered
config.yaml has changed from the previous published version. This avoids
churning Releases on every 3-hour cron run when nothing of substance
changed upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


def make_version_tag(ts: datetime | None = None) -> str:
    """Format a UTC timestamp as `vYYYY-MM-DD-HHMMSS`."""
    ts = ts or datetime.now(timezone.utc)
    return ts.strftime("v%Y-%m-%d-%H%M%S")


class ReleaseAPI(Protocol):
    def create_release(self, *, tag: str, name: str, body: str, files: list[Path]) -> dict: ...


class _NoopAPI:
    """Default API used outside GitHub Actions. Always reports success
    without actually creating a release. Used in local runs and tests."""

    def create_release(self, *, tag: str, name: str, body: str, files: list[Path]) -> dict:
        return {"html_url": f"local://{tag}", "tag": tag, "noop": True}


@dataclass
class ReleasePublisher:
    api: ReleaseAPI
    output_dir: Path
    config_path: Path

    @classmethod
    def default(cls, output_dir: Path, config_path: Path) -> "ReleasePublisher":
        """Build a publisher using the no-op API by default.

        The GitHub Actions workflow constructs a real API client at runtime
        using GITHUB_TOKEN; this default keeps the script runnable locally.
        """
        return cls(api=_NoopAPI(), output_dir=output_dir, config_path=config_path)

    def publish(
        self,
        *,
        version_tag: str,
        release_notes: str,
        previous_config_text: str,
    ) -> dict:
        current = self.config_path.read_text(encoding="utf-8")
        if current == previous_config_text:
            return {"skipped": True, "reason": "no changes detected", "tag": version_tag}
        result = self.api.create_release(
            tag=version_tag,
            name=version_tag,
            body=release_notes,
            files=[self.config_path],
        )
        return result

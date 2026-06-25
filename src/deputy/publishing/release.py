"""GitHub Releases publisher.

The publisher is conditional: it only creates a release when the rendered
``config.yaml`` has changed from the previously published version. This avoids
churning Releases on every 3-hour cron run when nothing of substance changed
upstream.

The ``ReleaseAPI`` Protocol is implemented by:

- ``_NoopAPI`` — default outside GitHub Actions; always reports success
  without actually creating a release. Used in local runs and tests.
- ``softprops/action-gh-release@v2`` — invoked by ``.github/workflows/
  sync-and-release.yml`` via ``softprops/action-gh-release``; the workflow
  injects ``GITHUB_TOKEN`` and the publisher delegates to the action through
  the workflow YAML rather than directly via the GitHub REST API.

Behavior is preserved verbatim from the legacy ``scripts/release_publisher.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


def make_version_tag(ts: datetime | None = None) -> str:
    """Format a UTC timestamp as ``vYYYY-MM-DD-HHMMSS``."""
    ts = ts or datetime.now(timezone.utc)
    return ts.strftime("v%Y-%m-%d-%H%M%S")


class ReleaseAPI(Protocol):
    """Pluggable backend used by ``ReleasePublisher.publish``."""

    def create_release(
        self, *, tag: str, name: str, body: str, files: list[Path]
    ) -> dict: ...


class _NoopAPI:
    """Default API used outside GitHub Actions.

    Always reports success without actually creating a release. Used in local
    runs and tests.
    """

    def create_release(self, *, tag: str, name: str, body: str, files: list[Path]) -> dict:
        return {"html_url": f"local://{tag}", "tag": tag, "noop": True}


@dataclass
class ReleasePublisher:
    """Conditional GitHub Releases publisher."""

    api: ReleaseAPI
    output_dir: Path
    config_path: Path

    @classmethod
    def default(cls, output_dir: Path, config_path: Path) -> "ReleasePublisher":
        """Build a publisher using the no-op API by default.

        The GitHub Actions workflow runs the actual release through the
        ``softprops/action-gh-release@v2`` step instead of invoking this
        publisher directly; the no-op default keeps the script runnable
        locally and in tests.
        """
        return cls(api=_NoopAPI(), output_dir=output_dir, config_path=config_path)

    def publish(
        self,
        *,
        version_tag: str,
        release_notes: str,
        previous_config_text: str,
    ) -> dict:
        """Publish only when the rendered config differs from the previous one."""
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

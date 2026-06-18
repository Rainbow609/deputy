"""Tests for release publisher — conditional GitHub Releases creation.

The publisher must skip the API call when the rendered config.yaml is
byte-identical to the previously published version. This avoids churning
the Releases list on every 3-hour cron run when nothing changed upstream.
"""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.release_publisher import ReleasePublisher, make_version_tag


def test_make_version_tag_uses_utc_timestamp():
    ts = datetime(2024, 6, 18, 12, 30, 45, tzinfo=timezone.utc)
    assert make_version_tag(ts) == "v2024-06-18-123045"


def test_make_version_tag_default_is_now():
    tag = make_version_tag()
    # Format: v + YYYY-MM-DD-HHMMSS = 1 + 10 + 1 + 2 + 1 + 2 + 1 + 6 = 18
    assert tag.startswith("v") and len(tag) == 18


def test_release_publisher_skips_when_unchanged(tmp_path):
    """If config.yaml hasn't changed, publisher should report no-op without calling the API."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("a: 1\n", encoding="utf-8")
    calls: list = []

    class FakeAPI:
        def create_release(self, **kwargs):
            calls.append(kwargs)
            return {"html_url": "https://x"}

    pub = ReleasePublisher(api=FakeAPI(), output_dir=tmp_path, config_path=cfg)
    pub.publish(
        version_tag="v2024-06-18-120000",
        release_notes="notes",
        previous_config_text="a: 1\n",  # same as current
    )
    assert calls == []  # no API call made


def test_release_publisher_creates_release_when_changed(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("a: 2\n", encoding="utf-8")
    calls: list = []

    class FakeAPI:
        def create_release(self, **kwargs):
            calls.append(kwargs)
            return {"html_url": "https://x/releases/v1"}

    pub = ReleasePublisher(api=FakeAPI(), output_dir=tmp_path, config_path=cfg)
    pub.publish(
        version_tag="v2024-06-18-120000",
        release_notes="notes",
        previous_config_text="a: 1\n",
    )
    assert len(calls) == 1
    assert calls[0]["tag"] == "v2024-06-18-120000"

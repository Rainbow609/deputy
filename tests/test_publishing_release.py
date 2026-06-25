"""Tests for release publisher — conditional GitHub Releases creation."""

from __future__ import annotations

from datetime import datetime, timezone

from deputy.publishing.release import ReleasePublisher, make_version_tag


def test_make_version_tag_uses_utc_timestamp():
    ts = datetime(2024, 6, 18, 12, 30, 45, tzinfo=timezone.utc)
    assert make_version_tag(ts) == "v2024-06-18-123045"


def test_make_version_tag_default_is_now():
    tag = make_version_tag()
    assert tag.startswith("v") and len(tag) == 18


def test_release_publisher_skips_when_unchanged(tmp_path):
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
        previous_config_text="a: 1\n",
    )
    assert calls == []


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
    assert calls[0]["name"] == "v2024-06-18-120000"
    assert calls[0]["files"] == [cfg]


def test_release_publisher_default_is_noop(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("a: 2\n", encoding="utf-8")
    pub = ReleasePublisher.default(output_dir=tmp_path, config_path=cfg)
    result = pub.publish(
        version_tag="v1", release_notes="n", previous_config_text="a: 1\n"
    )
    assert result["noop"] is True
    assert result["tag"] == "v1"

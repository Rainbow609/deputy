import io
from scripts.github_actions_logger import GhaLogger, LogLevel


def test_logger_writes_structured_output():
    buf = io.StringIO()
    logger = GhaLogger("deputy", output=buf)
    logger.set_level(LogLevel.INFO)
    logger.info("starting", {"sources": 3})
    out = buf.getvalue()
    assert "::group::" not in out  # info should not be a group
    assert "starting" in out


def test_logger_groups_for_debug():
    buf = io.StringIO()
    logger = GhaLogger("deputy", output=buf, is_github_actions=True)
    logger.set_level(LogLevel.DEBUG)
    with logger.group("fetch"):
        logger.debug("trying transport", {"url": "https://x"})
    out = buf.getvalue()
    assert "::group::fetch" in out
    assert "::endgroup::" in out


def test_logger_error_emits_github_annotation():
    buf = io.StringIO()
    logger = GhaLogger("deputy", output=buf, is_github_actions=True)
    logger.error("subscription failed", {"url": "https://x", "reason": "timeout"})
    assert "::error::subscription failed" in buf.getvalue()
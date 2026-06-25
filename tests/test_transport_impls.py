"""Tests for each concrete transport implementation."""

from __future__ import annotations

import sys
import types

import pytest

from deputy.transport.chain import TransportError, TransportResult
from deputy.transport.impls.cloudscraper import CloudscraperTransport
from deputy.transport.impls.curl_cffi import CurlCffiSafariTransport, CurlCffiTransport
from deputy.transport.impls.mihomo import MihomoTransport
from deputy.transport.impls.requests import RequestsTransport
from deputy.transport.impls.tls_client import TlsClientTransport


def _install_fake_module(name, **attrs):
    """Inject a fake module into ``sys.modules`` with the given attributes."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _remove_module(name):
    sys.modules.pop(name, None)


def test_cloudscraper_transport_calls_session(monkeypatch):
    fake_session = types.SimpleNamespace()
    fake_session.get = lambda url, **kw: types.SimpleNamespace(
        status_code=200, text="hello", content=b"hello"
    )
    _install_fake_module(
        "cloudscraper",
        create_scraper=lambda browser=None: fake_session,
        create_cloudScraper=lambda browser=None: fake_session,
    )
    t = CloudscraperTransport()
    result = t.fetch("https://example.com")
    assert result.status == 200
    assert result.text() == "hello"
    assert result.transport_name == "cloudscraper"


def test_cloudscraper_transport_raises_when_fetch_fails(monkeypatch):
    """If cloudscraper.create_scraper raises ImportError on first call, fetch raises."""
    class _Raising:
        def __getattr__(self, name):
            raise ImportError("simulated missing cloudscraper dependency")

    monkeypatch.setitem(sys.modules, "cloudscraper", _Raising())
    t = CloudscraperTransport()
    with pytest.raises(TransportError, match="cloudscraper"):
        t.fetch("https://example.com")


def test_cloudscraper_transport_available_true_when_installed(monkeypatch):
    """Available stays True when cloudscraper is importable and create_scraper works."""
    fake_session = types.SimpleNamespace()
    fake_session.get = lambda url, **kw: types.SimpleNamespace(
        status_code=200, text="ok", content=b"ok"
    )
    _install_fake_module(
        "cloudscraper",
        create_scraper=lambda browser=None: fake_session,
    )
    t = CloudscraperTransport()
    assert t.available is True


def test_requests_transport_calls_get(monkeypatch):
    fake_session = types.SimpleNamespace()
    fake_session.get = lambda url, **kw: types.SimpleNamespace(
        status_code=200, text="hi", content=b"hi"
    )
    _install_fake_module("requests", Session=lambda: fake_session)
    t = RequestsTransport()
    result = t.fetch("https://example.com")
    assert result.status == 200
    assert result.text() == "hi"
    assert result.transport_name == "requests"


def test_requests_transport_prefers_utf8_content_over_misdecoded_text(monkeypatch):
    fake_session = types.SimpleNamespace()
    fake_session.get = lambda url, **kw: types.SimpleNamespace(
        status_code=200,
        text="ä¸\xadå\x9b½",
        content="中国".encode("utf-8"),
    )
    _install_fake_module("requests", Session=lambda: fake_session)
    t = RequestsTransport()
    result = t.fetch("https://example.com")
    assert result.text() == "中国"


def test_curl_cffi_transport_calls_get(monkeypatch):
    fake_module = types.SimpleNamespace()
    captured_kwargs = {}

    def fake_get(url, **kw):
        captured_kwargs.update(kw)
        return types.SimpleNamespace(status_code=200, text="curl-ok", content=b"curl-ok")

    fake_module.get = fake_get
    fake_pkg = types.SimpleNamespace(requests=fake_module)
    sys.modules["curl_cffi"] = fake_pkg
    # Also create a valid spec so find_spec returns something.
    sys.modules["curl_cffi"].__spec__ = types.SimpleNamespace(name="curl_cffi")
    t = CurlCffiTransport()
    assert t.available is True
    result = t.fetch("https://example.com")
    assert result.status == 200
    assert result.text() == "curl-ok"
    assert result.transport_name == "curl_cffi"
    assert captured_kwargs.get("impersonate") == "chrome120"


def test_curl_cffi_transport_marks_unavailable_when_missing(monkeypatch):
    # Completely remove the module from sys.modules AND clear its spec cache.
    _remove_module("curl_cffi")
    # Patch find_spec to return None so importlib.util.find_spec("curl_cffi") -> None.
    import importlib.util as _ilu

    monkeypatch.setattr(_ilu, "find_spec", lambda name: None)
    t = CurlCffiTransport()
    assert t.available is False
    with pytest.raises(TransportError, match="curl_cffi not installed"):
        t.fetch("https://example.com")


def test_curl_cffi_safari_uses_safari_impersonate(monkeypatch):
    fake_module = types.SimpleNamespace()
    captured_kwargs = {}

    def fake_get(url, **kw):
        captured_kwargs.update(kw)
        return types.SimpleNamespace(status_code=200, text="safari-ok", content=b"safari-ok")

    fake_module.get = fake_get
    sys.modules["curl_cffi"] = types.SimpleNamespace(requests=fake_module)
    sys.modules["curl_cffi"].__spec__ = types.SimpleNamespace(name="curl_cffi")
    t = CurlCffiSafariTransport()
    assert t.name == "curl_cffi_safari"
    result = t.fetch("https://example.com")
    assert result.text() == "safari-ok"
    assert captured_kwargs.get("impersonate") == "safari17_0"


def test_mihomo_transport_strips_flag_clash_and_uses_clash_meta_ua(monkeypatch):
    fake_session = types.SimpleNamespace()
    captured_kwargs = {}

    def fake_get(url, **kw):
        captured_kwargs.update({"url": url, **kw})
        return types.SimpleNamespace(status_code=200, text="ok", content=b"ok")

    fake_session.get = fake_get
    _install_fake_module("requests", Session=lambda: fake_session)
    t = MihomoTransport()
    result = t.fetch("https://example.com/sub?flag=clash&token=abc")
    assert result.transport_name == "clash-meta"
    assert captured_kwargs["headers"]["User-Agent"] == "clash-meta"
    # flag=clash stripped from the URL
    assert "flag=clash" not in captured_kwargs["url"]
    # token is preserved (only flag=clash is stripped)
    assert "token=abc" in captured_kwargs["url"]


def test_mihomo_transport_passes_url_through_when_no_flag(monkeypatch):
    fake_session = types.SimpleNamespace()
    captured = {}

    def fake_get(url, **kw):
        captured["url"] = url
        return types.SimpleNamespace(status_code=200, text="ok", content=b"ok")

    fake_session.get = fake_get
    _install_fake_module("requests", Session=lambda: fake_session)
    t = MihomoTransport()
    t.fetch("https://example.com/sub")
    assert captured["url"] == "https://example.com/sub"


def test_mihomo_transport_strip_flag_clash_helper():
    t = MihomoTransport()
    # ?flag=clash at the end of query is stripped (no token preserved).
    assert t._strip_flag_clash("https://x.com?flag=clash") == "https://x.com"
    # ?flag=clash&token=y → token remains, flag=clash removed.
    assert t._strip_flag_clash("https://x.com?flag=clash&token=y") == "https://x.com?token=y"
    # token first, flag=clash last → flag=clash removed.
    assert t._strip_flag_clash("https://x.com?token=y&flag=clash") == "https://x.com?token=y"
    # No flag=clash → pass through.
    assert t._strip_flag_clash("https://x.com?token=y") == "https://x.com?token=y"


def test_tls_client_transport_marks_unavailable_when_missing(monkeypatch):
    _remove_module("tls_client")
    import importlib.util as _ilu

    monkeypatch.setattr(_ilu, "find_spec", lambda name: None)
    t = TlsClientTransport()
    assert t.available is False
    with pytest.raises(TransportError, match="tls_client not installed"):
        t.fetch("https://example.com")


def test_tls_client_transport_calls_session(monkeypatch):
    fake_session_mod = types.SimpleNamespace()
    fake_session_inst = types.SimpleNamespace()
    captured_kwargs = {}

    def fake_get(url, **kw):
        captured_kwargs.update(kw)
        return types.SimpleNamespace(status_code=200, text="tls-ok", content=b"tls-ok")

    fake_session_inst.get = fake_get
    fake_session_mod.Session = lambda **kw: fake_session_inst
    sys.modules["tls_client"] = fake_session_mod
    sys.modules["tls_client"].__spec__ = types.SimpleNamespace(name="tls_client")
    t = TlsClientTransport()
    assert t.available is True
    result = t.fetch("https://example.com")
    assert result.text() == "tls-ok"
    assert result.transport_name == "tls_client"

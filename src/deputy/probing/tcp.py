"""TCP reachability probing for subscription nodes.

Aligned with mihomo-config's ``probing/tcp.py``:

- ``tcp_check(proxy, timeout, retries, address_family)`` returns
  ``(proxy, ok, info)`` where ``info`` is either a dict of latency stats
  (``avg_ms``, ``min_ms``, ``max_ms``, ``variance``, ``jitter``, ``samples``)
  or a string failure reason.
- ``tcp_probe(proxies, ...)`` runs ``tcp_check`` concurrently and bundles the
  outcome into a frozen ``ProbeResult`` for the orchestration layer.
- ``NodeVerifier`` is preserved as a thin compatibility wrapper so that
  legacy callers and existing E2E tests keep working.
"""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProbeResult:
    alive: list[dict]
    dead: list[tuple[dict, str]]
    stats_by_name: dict[str, dict]


@dataclass
class SingleProbeResult:
    """Lightweight per-node probe record used by the legacy ``NodeVerifier``."""

    alive: bool
    latency_ms: float | None = None
    failure_reason: str | None = None
    address: tuple | None = None


def probe_family_value(address_family: str) -> int:
    if address_family == "ipv4":
        return socket.AF_INET
    if address_family == "ipv6":
        return socket.AF_INET6
    return socket.AF_UNSPEC


def classify_probe_failure(*, exc: BaseException | None = None, code: int | None = None) -> str:
    if isinstance(exc, socket.gaierror):
        return "dns-failed"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if code in {60, 110}:
        return "timeout"
    if code in {61, 111}:
        return "connection-refused"
    if code in {51, 65, 113}:
        return "unreachable"
    return "unknown-error"


# Public alias for legacy tests
classify_failure = classify_probe_failure


def resolve_probe_addresses(host: str, port: int, address_family: str) -> list[tuple]:
    """Resolve all (family, socktype, proto, sockaddr) candidates for a host."""
    infos = socket.getaddrinfo(
        host,
        int(port),
        probe_family_value(address_family),
        socket.SOCK_STREAM,
    )
    seen: set = set()
    result: list[tuple] = []
    for family, socktype, proto, _canonname, sockaddr in infos:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key)
        result.append((family, socktype, proto, sockaddr))
    return result


def resolve_addresses(host: str, port: int, address_family: str) -> list[tuple]:
    """Backwards-compatible alias returning (family, sockaddr) tuples only."""
    candidates = resolve_probe_addresses(host, port, address_family)
    return [(c[0], c[3]) for c in candidates]


def _make_tcp_socket(family: int, socktype: int, proto: int):
    try:
        s = socket.socket(family, socktype, proto)
    except TypeError:
        s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except (OSError, AttributeError):
        pass
    try:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (OSError, AttributeError):
        pass
    return s


def _compute_stats(latencies: list[float]) -> tuple[float, float]:
    n = len(latencies)
    if n == 0:
        return 0.0, 0.0
    mean = sum(latencies) / n
    variance = sum((x - mean) ** 2 for x in latencies) / n
    jitter = (
        sum(abs(latencies[i] - latencies[i - 1]) for i in range(1, n)) / (n - 1)
        if n > 1
        else 0.0
    )
    return variance, jitter


def tcp_check(
    proxy: dict,
    timeout: int = 3,
    retries: int = 0,
    address_family: str = "auto",
) -> tuple[dict, bool, dict | str]:
    """Probe a single proxy. Returns ``(proxy, ok, info)``.

    On success, ``info`` is a dict with ``avg_ms``, ``min_ms``, ``max_ms``,
    ``variance``, ``jitter``, ``samples``. On failure, ``info`` is a string
    describing why the connection was refused or unreachable.
    """
    host = proxy.get("server", "")
    port = proxy.get("port", 0)
    if not host or not port:
        return proxy, False, "missing-endpoint"

    try:
        candidates = resolve_probe_addresses(host, port, address_family)
    except Exception as exc:
        return proxy, False, classify_probe_failure(exc=exc)

    latencies: list[float] = []
    attempt_summaries: list[str] = []

    for _attempt_round in range(retries + 1):
        for family, socktype, proto, sockaddr in candidates:
            s = None
            try:
                s = _make_tcp_socket(family, socktype, proto)
                s.settimeout(timeout)
                start = time.monotonic()
                result = s.connect_ex(sockaddr)
                elapsed = time.monotonic() - start
                if result == 0:
                    latencies.append(elapsed)
                    break
                category = classify_probe_failure(code=result)
                attempt_summaries.append(f"{category} ({sockaddr[0]}:{sockaddr[1]})")
            except Exception as exc:
                category = classify_probe_failure(exc=exc)
                attempt_summaries.append(f"{category} ({sockaddr[0]}:{sockaddr[1]})")
            finally:
                if s is not None:
                    try:
                        s.close()
                    except OSError:
                        pass

    if latencies:
        vals_ms = [round(l * 1000, 1) for l in latencies]
        avg_ms = round(sum(vals_ms) / len(vals_ms), 1)
        variance_raw, jitter_raw = _compute_stats(latencies)
        return proxy, True, {
            "avg_ms": avg_ms,
            "min_ms": min(vals_ms),
            "max_ms": max(vals_ms),
            "variance": round(variance_raw * 1_000_000, 2),
            "jitter": round(jitter_raw * 1000, 2),
            "samples": len(vals_ms),
        }

    if attempt_summaries:
        return proxy, False, ", ".join(attempt_summaries)
    return proxy, False, "unknown-error"


def tcp_probe(
    proxies: list[dict],
    timeout: int = 3,
    concurrency: int = 30,
    retries: int = 0,
    address_family: str = "auto",
) -> ProbeResult:
    """Probe all proxies concurrently. Returns a frozen ``ProbeResult``."""
    ordered_results: list = [None] * len(proxies)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(tcp_check, proxy, timeout, retries, address_family): idx
            for idx, proxy in enumerate(proxies)
        }
        for f in as_completed(futures):
            ordered_results[futures[f]] = f.result()

    alive: list[dict] = []
    dead: list[tuple[dict, str]] = []
    stats_by_name: dict[str, dict] = {}
    for proxy, ok, info in ordered_results:
        if ok:
            alive.append(proxy)
            stats_by_name[proxy["name"]] = info  # type: ignore[assignment]
        else:
            dead.append((proxy, info))  # type: ignore[arg-type]
    return ProbeResult(alive=alive, dead=dead, stats_by_name=stats_by_name)


# ---------------------------------------------------------------------------
# Legacy ``NodeVerifier`` — thin wrapper used by old E2E tests. It composes
# ``tcp_check`` and returns ``SingleProbeResult`` instead of ``ProbeResult``.
# ---------------------------------------------------------------------------


class NodeVerifier:
    """Backwards-compatible per-node verifier used by older callers."""

    def __init__(self, *, timeout: int = 3, retries: int = 0, address_family: str = "auto"):
        self.timeout = timeout
        self.retries = retries
        self.address_family = address_family

    def _tcp_check(self, host: str, port: int) -> SingleProbeResult:
        addrs = resolve_addresses(host, port, self.address_family)
        if not addrs:
            return SingleProbeResult(alive=False, failure_reason="dns-failed")
        last: SingleProbeResult | None = None
        rounds = self.retries + 1
        for _ in range(rounds):
            for family, sockaddr in addrs:
                try:
                    s = socket.socket(family, socket.SOCK_STREAM)
                    s.settimeout(self.timeout)
                    start = time.perf_counter()
                    err = s.connect_ex(sockaddr)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    s.close()
                    if err == 0:
                        return SingleProbeResult(alive=True, latency_ms=elapsed_ms, address=sockaddr)
                    last = SingleProbeResult(
                        alive=False,
                        failure_reason=classify_probe_failure(code=err),
                        address=sockaddr,
                    )
                except socket.timeout:
                    last = SingleProbeResult(alive=False, failure_reason="timeout", address=sockaddr)
                except socket.gaierror:
                    last = SingleProbeResult(alive=False, failure_reason="dns-failed", address=sockaddr)
                except OSError as e:
                    last = SingleProbeResult(
                        alive=False,
                        failure_reason=classify_probe_failure(exc=e),
                        address=sockaddr,
                    )
        return last or SingleProbeResult(alive=False, failure_reason="unknown-error")

    def verify_node(self, node: dict) -> SingleProbeResult:
        server = node.get("server")
        port = node.get("port")
        if not server or not port:
            return SingleProbeResult(alive=False, failure_reason="missing-endpoint")
        return self._tcp_check(server, int(port))

    def verify_many(
        self, nodes: Iterable[dict], *, concurrency: int = 30
    ) -> list[tuple[dict, SingleProbeResult]]:
        results: list[tuple[dict, SingleProbeResult]] = []
        nodes = list(nodes)
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(self.verify_node, n): n for n in nodes}
            for fut in as_completed(futures):
                n = futures[fut]
                try:
                    results.append((n, fut.result()))
                except Exception as e:
                    results.append((n, SingleProbeResult(alive=False, failure_reason=f"exception:{e}")))
        return results


# Backwards-compatible alias: older tests import ``ProbeResult`` as a flat
# dataclass with these attributes; map to ``SingleProbeResult``.
ProbeResultLegacy = SingleProbeResult

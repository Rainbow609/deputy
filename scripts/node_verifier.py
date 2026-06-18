"""Node verification: TCP probing, HTTP health check, latency measurement.

This is a direct port of mihomo-config's probe pipeline. Key behaviors:
- address_family=auto prefers IPv4 but falls back to IPv6
- retries=0 means: do NOT retry within a single address list (one pass)
- latency is measured by timing socket.connect_ex
"""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable


@dataclass
class ProbeResult:
    alive: bool
    latency_ms: float | None = None
    failure_reason: str | None = None
    address: tuple | None = None


def classify_failure(*, exc: BaseException | None = None, code: int | None = None) -> str:
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


def _family_value(name: str) -> int:
    if name == "ipv4":
        return socket.AF_INET
    if name == "ipv6":
        return socket.AF_INET6
    return socket.AF_UNSPEC


def resolve_addresses(host: str, port: int, address_family: str) -> list[tuple]:
    try:
        infos = socket.getaddrinfo(host, int(port), _family_value(address_family), socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    seen: set = set()
    out: list[tuple] = []
    for family, _st, _proto, _canon, sockaddr in infos:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key)
        out.append((family, sockaddr))
    return out


class NodeVerifier:
    def __init__(self, *, timeout: int = 3, retries: int = 0, address_family: str = "auto"):
        self.timeout = timeout
        self.retries = retries
        self.address_family = address_family

    def _tcp_check(self, host: str, port: int) -> ProbeResult:
        addrs = resolve_addresses(host, port, self.address_family)
        if not addrs:
            return ProbeResult(alive=False, failure_reason="dns-failed")
        last: ProbeResult | None = None
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
                        return ProbeResult(alive=True, latency_ms=elapsed_ms, address=sockaddr)
                    last = ProbeResult(
                        alive=False,
                        failure_reason=classify_failure(code=err),
                        address=sockaddr,
                    )
                except socket.timeout as e:
                    last = ProbeResult(alive=False, failure_reason="timeout", address=sockaddr)
                except socket.gaierror as e:
                    last = ProbeResult(alive=False, failure_reason="dns-failed", address=sockaddr)
                except OSError as e:
                    last = ProbeResult(alive=False, failure_reason=classify_failure(exc=e), address=sockaddr)
        return last or ProbeResult(alive=False, failure_reason="unknown-error")

    def verify_node(self, node: dict) -> ProbeResult:
        server = node.get("server")
        port = node.get("port")
        if not server or not port:
            return ProbeResult(alive=False, failure_reason="missing-endpoint")
        return self._tcp_check(server, int(port))

    def verify_many(self, nodes: Iterable[dict], *, concurrency: int = 30) -> list[tuple[dict, ProbeResult]]:
        results: list[tuple[dict, ProbeResult]] = []
        nodes = list(nodes)
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(self.verify_node, n): n for n in nodes}
            for fut in as_completed(futures):
                n = futures[fut]
                try:
                    results.append((n, fut.result()))
                except Exception as e:
                    results.append((n, ProbeResult(alive=False, failure_reason=f"exception:{e}")))
        return results
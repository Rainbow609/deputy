"""Proxy health checks backed by Mihomo external controller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    delay_ms: int | None = None
    failure_reason: str | None = None


class MihomoDelayChecker:
    """Check proxy health through Mihomo's /proxies/{name}/delay endpoint."""

    def check(self, proxy: dict, config: Any) -> HealthCheckResult:
        if not config.enabled:
            return HealthCheckResult(ok=False, failure_reason="health-disabled")

        proxy_name = proxy.get("name")
        if not proxy_name:
            return HealthCheckResult(ok=False, failure_reason="missing-proxy-name")

        headers = {}
        if config.secret:
            headers["Authorization"] = f"Bearer {config.secret}"
        try:
            response = requests.get(
                f"{config.controller_url.rstrip('/')}/proxies/{proxy_name}/delay",
                params={
                    "url": config.test_url,
                    "timeout": config.timeout_ms,
                    "expected": config.expected,
                },
                headers=headers,
                timeout=max(1, config.timeout_ms / 1000),
            )
        except requests.Timeout:
            return HealthCheckResult(ok=False, failure_reason="timeout")
        except requests.RequestException as exc:
            return HealthCheckResult(ok=False, failure_reason=str(exc))

        if response.status_code == 200:
            data = response.json()
            return HealthCheckResult(ok=True, delay_ms=data.get("delay"))
        if response.status_code == 408:
            return HealthCheckResult(ok=False, failure_reason="timeout")
        return HealthCheckResult(ok=False, failure_reason=f"http-{response.status_code}")

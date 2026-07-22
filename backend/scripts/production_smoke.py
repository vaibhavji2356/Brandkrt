"""Bounded, read-only BrandKrt production smoke checks.

Credentials are optional and read only from environment variables. Nothing
sensitive is printed. This script never calls social/OpenAI providers.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

import httpx


REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


async def run(base_url: str, timeout: float) -> int:
    failures: list[str] = []
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout), follow_redirects=False,
    ) as client:
        live = await _request(client, "GET", "/api/health/live", failures, expected={200})
        ready = await _request(client, "GET", "/api/health/ready", failures, expected={200})
        anonymous = await _request(client, "GET", "/api/auth/me", failures, expected={401})
        for name, response in (("liveness", live), ("readiness", ready), ("anonymous auth", anonymous)):
            if response is not None:
                request_id = response.headers.get("x-request-id", "")
                if not REQUEST_ID.fullmatch(request_id):
                    failures.append(f"{name}: missing or unsafe X-Request-ID")
                if "traceback" in response.text.casefold():
                    failures.append(f"{name}: debug trace content detected")

        email = os.environ.get("BRANDKRT_SMOKE_EMAIL", "").strip()
        password = os.environ.get("BRANDKRT_SMOKE_PASSWORD", "")
        if email and password:
            login = await _request(
                client, "POST", "/api/auth/login", failures, expected={200},
                json={"email": email, "password": password, "remember_me": False},
            )
            if login is not None and login.status_code == 200:
                if "x-ratelimit-limit" not in login.headers:
                    failures.append("authenticated login: rate-limit headers missing")
                for path in (
                    "/api/auth/me", "/api/creator-commercial/profiles",
                    "/api/campaign-performance", "/api/creator-commercial/audit-events",
                ):
                    await _request(client, "GET", path, failures, expected={200})
                await _request(
                    client, "GET", "/api/campaign-evidence/000000000000000000000000",
                    failures, expected={404},
                )

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: bounded read-only production smoke checks completed")
    return 0


async def _request(client, method: str, path: str, failures: list[str], expected: set[int], **kwargs):
    try:
        response = await client.request(method, path, **kwargs)
    except (httpx.TimeoutException, httpx.TransportError):
        failures.append(f"{method} {path}: transport failure")
        return None
    if response.status_code not in expected:
        failures.append(f"{method} {path}: expected {sorted(expected)}, received {response.status_code}")
    if len(response.content) > 2 * 1024 * 1024:
        failures.append(f"{method} {path}: response exceeded 2 MB")
    return response


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only BrandKrt production smoke checks")
    parser.add_argument("--base-url", default=os.environ.get("BRANDKRT_SMOKE_BASE_URL", ""))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("BRANDKRT_SMOKE_TIMEOUT_SECONDS", "12")))
    args = parser.parse_args(argv)
    if not args.base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        print("FAIL: provide an HTTPS base URL or a local development URL")
        return 2
    if not 1 <= args.timeout <= 30:
        print("FAIL: timeout must be between 1 and 30 seconds")
        return 2
    return asyncio.run(run(args.base_url, args.timeout))


if __name__ == "__main__":
    sys.exit(main())

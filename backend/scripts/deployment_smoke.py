"""Deployment smoke checks for a running Market instance.

The script uses only the Python standard library so it can run on a fresh
server after Docker deployment without installing project dependencies.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any


class SmokeFailure(Exception):
    pass


class SmokeClient:
    def __init__(self, base_url: str, *, insecure: bool = False, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.context = ssl._create_unverified_context() if insecure else None
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]
        if self.context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=self.context))
        self.opener = urllib.request.build_opener(*handlers)

    def request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        expected: set[int] | None = None,
    ) -> tuple[int, Any]:
        expected = expected or {200}
        body = None
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = self.base_url + path
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=self.timeout)
            status = response.getcode()
            payload = self._read_json(response)
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = self._read_json(exc)
        except Exception as exc:  # noqa: BLE001
            raise SmokeFailure(f"{method} {path} failed: {exc}") from exc
        if status not in expected:
            raise SmokeFailure(f"{method} {path} returned {status}, expected {sorted(expected)}: {payload}")
        return status, payload

    @staticmethod
    def _read_json(response: Any) -> Any:
        raw = response.read()
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text[:500]


def wait_until_ready(client: SmokeClient, retries: int, interval: float) -> None:
    last_error = ""
    for _ in range(retries):
        try:
            _, payload = client.request("GET", "/api/ready", expected={200})
            if isinstance(payload, dict) and payload.get("status") == "ready":
                return
        except SmokeFailure as exc:
            last_error = str(exc)
        time.sleep(interval)
    raise SmokeFailure(f"service is not ready after {retries} retries: {last_error}")


def run(args: argparse.Namespace) -> None:
    client = SmokeClient(args.base_url, insecure=args.insecure, timeout=args.timeout)
    wait_until_ready(client, args.retries, args.interval)

    _, health = client.request("GET", "/api/health", expected={200})
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise SmokeFailure(f"health payload invalid: {health}")

    client.request("GET", "/api/settings/system", expected={401, 403})

    _, login = client.request(
        "POST",
        "/api/auth/login",
        data={"username": args.username, "password": args.password},
        expected={200},
    )
    if not isinstance(login, dict) or not login.get("user"):
        raise SmokeFailure(f"login payload invalid: {login}")

    _, me = client.request("GET", "/api/auth/me", expected={200})
    if not isinstance(me, dict) or not me.get("username"):
        raise SmokeFailure(f"current user payload invalid: {me}")

    _, system = client.request("GET", "/api/settings/system", expected={200})
    if not isinstance(system, dict) or "data_stats" not in system:
        raise SmokeFailure(f"system payload invalid: {system}")

    _, crawler_status = client.request("GET", "/api/crawlers/status", expected={200})
    if not isinstance(crawler_status, list):
        raise SmokeFailure(f"crawler status payload invalid: {crawler_status}")

    _, aipaas = client.request("GET", "/api/aipaas-sync/config", expected={200})
    if not isinstance(aipaas, dict) or "sync_users" not in aipaas:
        raise SmokeFailure(f"aipaas config payload invalid: {aipaas}")

    print("SMOKE PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deployment smoke checks against a live Market instance.")
    parser.add_argument("--base-url", required=True, help="Base URL, for example https://market.company.com")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification for internal CAs")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--retries", type=int, default=30)
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()
    try:
        run(args)
    except SmokeFailure as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

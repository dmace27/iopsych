"""Loopback-only packaging probes; no data writes, tokens, or external services."""

import json
from urllib.error import HTTPError
from urllib.request import urlopen


def get(url: str) -> tuple[int, bytes]:
    try:
        with urlopen(url, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


status, body = get("http://127.0.0.1:8106/health")
assert status == 200 and json.loads(body)["status"] == "ok", (status, body)
status, body = get("http://127.0.0.1:3106/")
assert status == 200 and b"<html" in body, status
status, _ = get("http://127.0.0.1:3106/api/internal/auth/me")
assert status in (401, 403), status
print("PASS: API liveness, production web HTML, unauthenticated web proxy denial")

"""Local-only live Next Host regression; run directly with Python, no DB required."""

import http.client
import json
import os
import signal
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]


class MockAPI(BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self) -> None:
        assert self.path == "/v1/auth/local-login"
        self.rfile.read(int(self.headers["Content-Length"]))
        type(self).calls += 1
        payload = b'{"access_token":"synthetic-local-test-placeholder"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        pass


def request(headers: dict[str, str]) -> tuple[int, bool]:
    connection = http.client.HTTPConnection("127.0.0.1", 3113, timeout=30)
    try:
        connection.request(
            "POST",
            "/api/session/local",
            body=json.dumps({"identity": "alpha"}),
            headers={"Content-Type": "application/json", **headers},
        )
        response = connection.getresponse()
        result = response.status, response.getheader("Set-Cookie") is not None
        response.read()
        return result
    finally:
        connection.close()


def main() -> None:
    # Refuse occupied allocations; never send probes to an existing worker.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 3113))
    server = HTTPServer(("127.0.0.1", 8113), MockAPI)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(
                ["npm", "run", "dev:web"],
                cwd=ROOT,
                env={
                    **os.environ,
                    "LOCAL_LOGIN_ENABLED": "true",
                    "API_BASE_URL": "http://127.0.0.1:8113",
                    "WEB_HOST": "127.0.0.1",
                    "WEB_PORT": "3113",
                },
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            try:
                for _ in range(200):
                    assert process.poll() is None, "Next exited before becoming ready"
                    try:
                        with socket.create_connection(("127.0.0.1", 3113), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AssertionError("Next did not become ready")
                cases = [
                    (
                        "loopback control",
                        {"Host": "127.0.0.1:3113", "Origin": "http://127.0.0.1:3113"},
                        200,
                        True,
                        1,
                    ),
                    (
                        "hostile Host and matching Origin",
                        {
                            "Host": "rebind.example.invalid:3113",
                            "Origin": "http://rebind.example.invalid:3113",
                        },
                        404,
                        False,
                        0,
                    ),
                    (
                        "hostile Host and Fetch Metadata",
                        {"Host": "rebind.example.invalid:3113", "Sec-Fetch-Site": "same-origin"},
                        404,
                        False,
                        0,
                    ),
                    (
                        "hostile Host with forged forwarding",
                        {
                            "Host": "rebind.example.invalid:3113",
                            "Origin": "http://rebind.example.invalid:3113",
                            "X-Forwarded-Host": "127.0.0.1:3113",
                            "Forwarded": "host=127.0.0.1:3113",
                        },
                        404,
                        False,
                        0,
                    ),
                    (
                        "loopback cross-origin",
                        {"Host": "127.0.0.1:3113", "Origin": "http://evil.example.invalid"},
                        403,
                        False,
                        0,
                    ),
                ]
                for name, headers, status, cookie, calls in cases:
                    before = MockAPI.calls
                    actual = request(headers)
                    delta = MockAPI.calls - before
                    assert actual == (status, cookie), (name, actual)
                    assert delta == calls, (name, delta)
                    print(f"{name}: status={status}, cookie={cookie}, upstream_calls={delta}")
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()

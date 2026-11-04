"""Rehearse the running local synthetic web session without printing credentials."""

import os
from urllib.parse import urlsplit

import httpx

web = os.environ.get("LOCAL_WEB_ORIGIN", "http://127.0.0.1:3101")
api = os.environ.get("LOCAL_API_ORIGIN", "http://127.0.0.1:8101")
for origin in (web, api):
    parsed = urlsplit(origin)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("This verification is restricted to local HTTP origins")

with httpx.Client(base_url=web, timeout=60) as client:
    assert client.get(f"{api}/health").status_code == 200
    assert client.get("/api/health").status_code == 200
    page = client.get("/sign-in")
    assert page.status_code == 200 and "Synthetic local account" in page.text
    for identity, email, other_role in (
        ("alpha", "recruiter@alpha.example.invalid", "00000000-0000-4000-8000-000000000022"),
        ("beacon", "manager@beacon.example.invalid", "00000000-0000-4000-8000-000000000021"),
    ):
        response = client.post(
            "/api/session/local", json={"identity": identity}, headers={"Origin": web}
        )
        assert response.status_code == 200, "Local login failed: check seed and opt-in policy"
        assert response.json() == {"status": "ok"}
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=900" in cookie
        me = client.get("/api/internal/auth/me")
        assert me.status_code == 200 and me.json()["email"] == email
        assert client.get("/api/internal/roles").status_code == 200
        assert client.get(f"/api/internal/roles/{other_role}").status_code == 404
        assert client.get("/roles").status_code == 200
        print(f"{identity}: synthetic session and cross-tenant denial verified")
    assert client.delete("/api/session", headers={"Origin": web}).status_code == 204
    assert client.get("/api/internal/auth/me").status_code == 401
print("Local HTTP rehearsal passed; no credentials written or printed")

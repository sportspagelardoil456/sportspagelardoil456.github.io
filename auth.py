# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# ---
"""HTTP Basic Auth for the admin dashboard + /api routes."""

from __future__ import annotations

import base64
import logging
import os
import secrets
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("slack_mcp_gateway.auth")

_REALM = 'Basic realm="Slack WxO Gateway Admin", charset="UTF-8"'


def admin_credentials() -> Optional[tuple[str, str]]:
    """Return (user, password) when GATEWAY_ADMIN_USER + GATEWAY_ADMIN_PASSWORD are set."""
    user = (os.getenv("GATEWAY_ADMIN_USER") or "").strip()
    password = (os.getenv("GATEWAY_ADMIN_PASSWORD") or "").strip()
    if user and password:
        return user, password
    return None


def auth_required() -> bool:
    """True when admin credentials are configured (or explicitly required)."""
    if admin_credentials():
        return True
    return (os.getenv("GATEWAY_REQUIRE_AUTH") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _unauthorized(message: str = "Authentication required") -> Response:
    return Response(
        content=message,
        status_code=401,
        headers={"WWW-Authenticate": _REALM, "Cache-Control": "no-store"},
        media_type="text/plain",
    )


def check_admin_auth(request: Request) -> Optional[Response]:
    """
    Return a 401 Response if the request is not authorized.
    Return None if access is allowed.

    - If GATEWAY_ADMIN_USER/PASSWORD are set → Basic auth required.
    - If GATEWAY_REQUIRE_AUTH is set without credentials → 503 (misconfigured).
    - Otherwise (local/dev) → open access.
    """
    creds = admin_credentials()
    if not creds:
        if auth_required():
            log.error("GATEWAY_REQUIRE_AUTH set but GATEWAY_ADMIN_USER/PASSWORD missing")
            return JSONResponse(
                {"error": "admin auth not configured on server"},
                status_code=503,
            )
        return None

    user, password = creds
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("basic "):
        return _unauthorized()

    try:
        raw = base64.b64decode(header.split(" ", 1)[1].strip()).decode("utf-8")
        got_user, got_pass = raw.split(":", 1)
    except Exception:
        return _unauthorized("Invalid Authorization header")

    user_ok = secrets.compare_digest(got_user, user)
    pass_ok = secrets.compare_digest(got_pass, password)
    if user_ok and pass_ok:
        return None
    return _unauthorized("Invalid username or password")

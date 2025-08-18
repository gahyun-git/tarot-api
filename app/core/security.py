import hashlib
import hmac
import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-XSS-Protection", "0")
        return response


def _consteq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


async def require_api_auth(request: Request) -> None:
    if not settings.auth_required:
        return
    # API Key check
    api_key_req = request.headers.get("x-api-key")
    if settings.api_key and api_key_req and _consteq(api_key_req, settings.api_key):
        return
    # HMAC check
    cid = request.headers.get("x-client-id")
    ts = request.headers.get("x-timestamp")
    sig = request.headers.get("x-signature")
    if not (cid and ts and sig and settings.hmac_secret):
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        ts_int = int(ts)
    except Exception as err:
        raise HTTPException(status_code=401, detail="invalid timestamp") from err
    if abs(int(time.time() * 1000) - ts_int) > 5 * 60 * 1000:
        raise HTTPException(status_code=401, detail="stale request")
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    # Canonicalize path to avoid signature mismatches due to trailing slashes
    path = request.url.path
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    base = f"{request.method}\n{path}\n{ts}\n{body_hash}"
    calc = hmac.new(settings.hmac_secret.encode(), base.encode(), hashlib.sha256).hexdigest()
    if not _consteq(calc, sig):
        raise HTTPException(status_code=401, detail="bad signature")

"""HTTP hardening (docs/SECURITY.md, T11): security headers on every response, and a per-IP
rate limit on POST requests (uploads are what costs CPU). Both are plain middleware, no dependency.

In-memory limiter: fine for one backend process (the hackathon setup); behind several workers
or a proxy, move it to the reverse proxy.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

# The API only returns JSON, images and PDFs — nothing in it ever needs to run a script or be framed.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
# Swagger UI (/docs, /redoc) loads its JS/CSS from a CDN; keep those pages working, still unframeable.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()
WINDOW_S = 60.0


def reset_rate_limit() -> None:
    with _lock:
        _hits.clear()


def _too_many(ip: str) -> float | None:
    """Seconds to wait if ip is over the limit, else None (and the request is counted)."""
    limit = settings.rate_limit_per_min
    if limit <= 0:
        return None
    now = time.monotonic()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > WINDOW_S:
            q.popleft()
        if len(q) >= limit:
            return WINDOW_S - (now - q[0])
        q.append(now)
    return None


def install(app: FastAPI) -> None:
    """Call before adding CORS, so CORS stays outermost and a 429 still carries CORS headers."""

    @app.middleware("http")
    async def harden(request: Request, call_next):
        if request.method == "POST":
            ip = request.client.host if request.client else "unknown"
            wait = _too_many(ip)
            if wait is not None:
                response = JSONResponse({"detail": "Too many requests, slow down"}, status_code=429,
                                        headers={"Retry-After": str(int(wait) + 1)})
                return _add_headers(request, response)
        return _add_headers(request, await call_next(request))


def _add_headers(request: Request, response):
    response.headers.update(HEADERS)
    if not request.url.path.startswith(DOCS_PATHS):
        # JSON only: the passport PDF opens as a top-level tab, and a 'none' policy can blank
        # the browser's built-in PDF viewer. PNG/PDF responses still get nosniff + no framing.
        if response.headers.get("content-type", "").startswith("application/json"):
            response.headers["Content-Security-Policy"] = API_CSP
        response.headers.setdefault("Cache-Control", "no-store")  # medical images: no shared caches
    if request.url.scheme == "https":  # HSTS only means something over TLS (production, behind a proxy)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

# Swagger UI loads scripts and styles from a CDN, so the strict policy below
# would break it. Everything else is pure JSON and needs nothing at all.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

SECURITY_HEADERS = {
    # Don't let the browser guess a different content type (MIME sniffing).
    "X-Content-Type-Options": "nosniff",
    # Never render the API inside a frame on another site (clickjacking).
    "X-Frame-Options": "DENY",
    # Don't send our URLs (which may contain ids) to other sites.
    "Referrer-Policy": "no-referrer",
    # Responses contain personal data: don't keep them in shared caches.
    "Cache-Control": "no-store",
    # Once a browser has seen HTTPS, it must keep using HTTPS for 2 years.
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"


async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", API_CSP)
    return response

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import settings
from src.services.audit_service import audit_service
from src.services.rbac_service import rbac_service


PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()

        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS or not request.url.path.startswith("/api"):
            response = await call_next(request)
            self._add_security_headers(response, start)
            return response

        # Token authentication (RBAC)
        token = request.headers.get("X-API-Token", "")
        user = None

        # Legacy API_TOKEN fallback
        if settings.API_TOKEN and token == settings.API_TOKEN:
            user = rbac_service.get_user("admin") or rbac_service.authenticate_token(token)
        elif token:
            user = rbac_service.authenticate_token(token)

        if user:
            request.state.user = user.username
            request.state.role = user.role.value
        elif settings.API_TOKEN and not token:
            # No token but API_TOKEN is set — allow with anonymous context
            request.state.user = "anonymous"
            request.state.role = "viewer"
        elif not settings.API_TOKEN:
            # No auth configured — allow all
            request.state.user = "system"
            request.state.role = "admin"

        response = await call_next(request)
        self._add_security_headers(response, start)

        if request.url.path.startswith("/api"):
            audit_service.write(
                getattr(request.state, "user", "system"),
                "http.request",
                request.url.path,
                {
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
        return response

    @staticmethod
    def _add_security_headers(response: Response, start: float) -> None:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))

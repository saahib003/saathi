"""HTTP protections for the local API."""

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.config import Settings


def _origin_is_allowed(request: Request, settings: Settings) -> bool:
    origin = request.headers.get("origin")
    return origin is not None and origin in settings.allowed_origins


class LocalApiGuard:
    """Require an allowed browser origin and bearer token on every /api request."""

    def __init__(self, app: Callable[..., Awaitable[object]], settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if not _origin_is_allowed(request, self.settings):
            response = JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
            await response(scope, receive, send)
            return

        # CORS preflight has no bearer token. Let CORSMiddleware answer it;
        # the actual API request remains token-protected below.
        if request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        authorization = request.headers.get("authorization", "")
        expected = f"Bearer {self.settings.app_session_token}"
        if authorization != expected:
            response = JSONResponse({"detail": "Missing or invalid session token"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

from fastapi import Request, Response, status
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


class OriginValidationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin not in self.allowed_origins:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Origine de requête refusée."},
                )
        return await call_next(request)

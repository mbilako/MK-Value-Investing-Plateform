import json
import logging
import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def configure_access_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("mkvip.access")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, log_level: str) -> None:
        super().__init__(app)
        self._logger = configure_access_logging(log_level)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied_request_id = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid.uuid4())
        )
        request.state.request_id = request_id
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self._logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                    separators=(",", ":"),
                )
            )

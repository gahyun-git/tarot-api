import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response

logger = logging.getLogger(__name__)


async def request_id_middleware(request: Request, call_next: Callable):
    # Body size guard (Content-Length fast path)
    from app.core.config import settings
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > settings.max_body_bytes:
        from starlette.responses import PlainTextResponse
        return PlainTextResponse("Payload Too Large", status_code=413)
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    request.state.request_id = request_id
    start = time.time()
    response: Response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled error",
            extra={
                "request_id": request_id,
                "client_ip": request.client.host if request.client else None,
                "path": request.url.path,
                "method": request.method,
            },
        )
        raise
    duration_ms = int((time.time() - start) * 1000)
    response.headers["x-request-id"] = request_id
    logger.info(
        "HTTP %s %s %s %dms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "request_id": request_id,
            "client_ip": request.client.host if request.client else None,
            "path": request.url.path,
            "method": request.method,
            "duration_ms": duration_ms,
        },
    )
    return response

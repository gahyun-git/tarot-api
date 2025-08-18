from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def http_error_handler(request: Request, exc: Exception):
    status = getattr(exc, "status_code", 500)
    code = getattr(exc, "code", "internal_error")
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": str(exc),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


def validation_error_handler(request: Request, exc: RequestValidationError):
    raw = exc.errors()
    details = []
    for e in raw:
        item = dict(e)
        ctx = item.get("ctx")
        if ctx is not None:
            item["ctx"] = {k: str(v) for k, v in ctx.items()}
        details.append(item)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request",
                "details": details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )

from fastapi import APIRouter, Request
from app.core.rate_limit import limiter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
@limiter.limit("5/second")
def health(request: Request):
    return {"status": "ok"}

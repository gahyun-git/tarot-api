from fastapi import APIRouter, Request
from app.core.rate_limit import limiter
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
@limiter.limit(settings.rate_limit_health)
def health(request: Request):
    return {"status": "ok"}

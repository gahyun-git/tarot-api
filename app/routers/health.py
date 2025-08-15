from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.rate_limit import limiter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
@limiter.limit(settings.rate_limit_health)
def health(request: Request):
    return {"status": "ok"}

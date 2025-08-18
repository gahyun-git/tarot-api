from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

storage_uri = settings.redis_url if settings.redis_url else None
if storage_uri:
    try:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[settings.rate_limit_default],
            storage_uri=storage_uri,
        )
    except Exception:
        # Fallback to in-memory limiter if remote store is unavailable
        limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])
else:
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])

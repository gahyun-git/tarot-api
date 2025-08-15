from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

storage_uri = settings.redis_url if settings.redis_url else None
if storage_uri:
    # Lazy import to avoid hard dependency
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default], storage_uri=storage_uri)
else:
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])
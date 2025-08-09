from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import request_id_middleware
from app.core.errors import http_error_handler
from app.core.rate_limit import limiter
from app.core.security import SecurityHeadersMiddleware
from app.services.deck_loader import DeckLoader
from app.routers import health, cards, reading


def create_app() -> FastAPI:
    setup_logging(settings.log_level)

    app = FastAPI(title="Tarot API", version="0.1.0")

    # Middleware: CORS → RequestID → RateLimit
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_id_middleware)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # Error handler
    from fastapi.exceptions import RequestValidationError
    from app.core.errors import validation_error_handler

    app.add_exception_handler(Exception, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.state.deck_loader = DeckLoader(settings.data_path)
    app.include_router(health.router)
    app.include_router(cards.router)
    app.include_router(reading.router)

    return app


app = create_app()

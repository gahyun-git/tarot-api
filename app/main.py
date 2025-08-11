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
from app.core.security import SecurityHeadersMiddleware, require_api_auth
from app.services.deck_loader import DeckLoader
from app.services.reading_repository import ReadingRepository, PostgresReadingRepository
from app.routers import health, cards, reading
from fastapi.staticfiles import StaticFiles


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
    # Auth (optional): protect mutating endpoints via dependency in routers

    # Error handler
    from fastapi.exceptions import RequestValidationError
    from app.core.errors import validation_error_handler

    app.add_exception_handler(Exception, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.state.deck_loader = DeckLoader(
        settings.data_path,
        settings.meanings_path,
        prefer_local_images=settings.prefer_local_images,
    )
    # Choose repository (DB or in-memory)
    if settings.use_db and settings.db_url:
        try:
            app.state.reading_repo = PostgresReadingRepository(settings.db_url)
        except Exception:
            # Fallback to in-memory if DB init fails
            app.state.reading_repo = ReadingRepository()
    else:
        app.state.reading_repo = ReadingRepository()
    # Validate CORS in non-local env
    if settings.env in {"dev", "prod"}:
        if not settings.cors_origins:
            raise RuntimeError("CORS_ORIGINS must be set in dev/prod environments")

    # Warm-up deck loading to avoid first-request latency
    try:
        app.state.deck_loader.load()
    except Exception:
        # Fail fast on startup if deck cannot be loaded
        raise
    app.include_router(health.router)
    app.include_router(cards.router)
    app.include_router(reading.router)

    # Static files for local images
    app.mount("/static", StaticFiles(directory="static"), name="static")

    return app


app = create_app()

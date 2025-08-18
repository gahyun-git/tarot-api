from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.deps import get_deck_loader, get_reading_repo
from app.core.rate_limit import limiter
from app.core.security import require_api_auth
from app.schemas.reading import (
    DailyFortuneResponse,
    FullReadingResult,
    InterpretRequest,
    InterpretResponse,
    ReadingRequest,
    ReadingResponse,
    SpreadInfo,
    SpreadsResponse,
)
from app.services.reading_api_service import (
    FullResultParams,
    create_and_save_reading,
    daily_fortune_result,
    get_full_result as service_get_full_result,
    interpret_and_cache,
)
from app.services.reading_repository import ReadingRepository

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/", response_model=ReadingResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def reading(request: Request, payload: ReadingRequest | None = None):
    deck = get_deck_loader(request)
    repo = get_reading_repo(request)
    assert payload is not None
    return create_and_save_reading(repo, deck, payload)


@router.get("/{reading_id:uuid}", response_model=ReadingResponse)
@limiter.limit(settings.rate_limit_cards)
def get_reading(request: Request, reading_id: UUID):
    repo = get_reading_repo(request)
    found = repo.get(str(reading_id))
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    return found


@router.post(
    "/{reading_id:uuid}/interpret",
    response_model=InterpretResponse,
    dependencies=[Depends(require_api_auth)],
)
@limiter.limit(settings.rate_limit_reading_post)
def interpret_reading(request: Request, reading_id: UUID, payload: InterpretRequest):
    repo = get_reading_repo(request)
    try:
        return interpret_and_cache(repo, str(reading_id), payload, settings.google_api_key)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="reading not found") from err


@router.get("/{reading_id:uuid}/result", response_model=FullReadingResult)
@limiter.limit(settings.rate_limit_cards)
def get_full_result(
    request: Request, reading_id: UUID, lang: str = "auto", use_llm: bool = False
):
    repo = get_reading_repo(request)
    deck = get_deck_loader(request)
    try:
        params = FullResultParams(
            repo, deck, str(reading_id), lang, use_llm, settings.google_api_key
        )
        return service_get_full_result(params)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="reading not found") from err


@router.get("/daily", response_model=DailyFortuneResponse)
@limiter.limit(settings.rate_limit_cards)
def daily_fortune(
    request: Request, lang: str = "auto", seed: int | None = None, use_llm: bool = False
):
    deck = get_deck_loader(request)
    return daily_fortune_result(deck, lang, seed, use_llm, settings.google_api_key)


@router.get("/spreads", response_model=SpreadsResponse)
@limiter.limit(settings.rate_limit_cards)
def list_spreads(request: Request):
    # 기본 8장 스프레드와 1장(오늘의 운세)
    items = [
        SpreadInfo(code="daily", name="Daily One Card", positions={1: "Issue"}).model_dump(),
        SpreadInfo(
            code="8-basic",
            name="Eight Positions",
            positions={
                1: "Issue",
                2: "Hidden Influence",
                3: "Past",
                4: "Present",
                5: "Near Future",
                6: "Inner",
                7: "Outer",
                8: "Solution",
            },
        ).model_dump(),
    ]
    return JSONResponse(content={"items": items})


@router.get("/s/{slug}")
@limiter.limit(settings.rate_limit_cards)
def resolve_share(request: Request, slug: str):
    repo: ReadingRepository = get_reading_repo(request)
    rid = repo.resolve_share_slug(slug)
    if not rid:
        raise HTTPException(status_code=404, detail="share link not found")
    return {"reading_id": rid}


@router.get("/s/{slug}/reading", response_model=ReadingResponse)
@limiter.limit(settings.rate_limit_cards)
def get_reading_by_slug(request: Request, slug: str):
    repo: ReadingRepository = get_reading_repo(request)
    rid = repo.resolve_share_slug(slug)
    if not rid:
        raise HTTPException(status_code=404, detail="share link not found")
    found = repo.get(rid)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    return found


@router.get("/s/{slug}/result", response_model=FullReadingResult)
@limiter.limit(settings.rate_limit_cards)
def get_result_by_slug(request: Request, slug: str, lang: str = "ko", use_llm: bool = False):
    repo: ReadingRepository = get_reading_repo(request)
    deck = get_deck_loader(request)
    rid = repo.resolve_share_slug(slug)
    if not rid:
        raise HTTPException(status_code=404, detail="share link not found")
    params = FullResultParams(repo, deck, rid, lang, use_llm, settings.google_api_key)
    try:
        return service_get_full_result(params)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="reading not found") from err


@router.post("/s/{slug}/interpret", response_model=InterpretResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def interpret_by_slug(request: Request, slug: str, payload: InterpretRequest):
    repo: ReadingRepository = get_reading_repo(request)
    rid = repo.resolve_share_slug(slug)
    if not rid:
        raise HTTPException(status_code=404, detail="share link not found")
    try:
        return interpret_and_cache(repo, rid, payload, settings.google_api_key)
    except ValueError as err:
        raise HTTPException(status_code=404, detail="reading not found") from err


@router.post("/{reading_id:uuid}/share")
@limiter.limit(settings.rate_limit_cards)
def create_share(request: Request, reading_id: UUID):
    repo: ReadingRepository = get_reading_repo(request)
    found = repo.get(str(reading_id))
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    slug = repo.create_share_slug(str(reading_id))
    return {"slug": slug}

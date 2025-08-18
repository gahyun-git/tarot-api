import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.deps import get_deck_loader, get_reading_repo
from app.core.rate_limit import limiter
from app.core.security import require_api_auth
from app.schemas.cards import Card
from app.schemas.reading import (
    CardWithContext,
    DailyFortuneResponse,
    DrawnCard,
    FullReadingResult,
    InterpretRequest,
    InterpretResponse,
    ReadingRequest,
    ReadingResponse,
    SpreadInfo,
    SpreadsResponse,
)
from app.services.interpret_service import (
    detect_lang,
    explain_cards_with_llm,
    interpret_local,
    interpret_with_llm,
)
from app.services.reading_service import create_reading

router = APIRouter(prefix="/reading", tags=["reading"])


def _role_map_for_lang(lang_norm: str) -> dict[int, str]:
    roles_ko = {1: "이슈", 2: "숨은 영향", 3: "과거", 4: "현재", 5: "근미래", 6: "내면", 7: "외부", 8: "솔루션"}
    roles_en = {1: "Issue", 2: "Hidden Influence", 3: "Past", 4: "Present", 5: "Near Future", 6: "Inner", 7: "Outer", 8: "Solution"}
    roles_ja = {1: "課題", 2: "潜在的影響", 3: "過去", 4: "現在", 5: "近未来", 6: "内面", 7: "外部", 8: "ソリューション"}
    roles_zh = {1: "议题", 2: "潜在影响", 3: "过去", 4: "现在", 5: "近未来", 6: "内在", 7: "外在", 8: "解决方案"}
    lang_key = (lang_norm or "en").lower()
    if lang_key.startswith("zh"):
        return roles_zh
    if lang_key == "ko":
        return roles_ko
    if lang_key == "ja":
        return roles_ja
    return roles_en


def _build_items_with_context(found: ReadingResponse, deck, lang_norm: str) -> list[CardWithContext]:
    items: list[CardWithContext] = []
    role_map = _role_map_for_lang(lang_norm)
    for it in found.items:
        meanings = deck.get_meanings(it.card.id, lang_norm, it.is_reversed)
        items.append(
            CardWithContext(
                position=it.position,
                role=role_map.get(it.position, ""),
                is_reversed=it.is_reversed,
                used_meanings=(meanings[:3] if meanings else None),
                card=it.card,
            )
        )
    return items


def _load_or_compute_interpretation(repo, found: ReadingResponse, lang_norm: str, use_llm: bool) -> InterpretResponse:
    cached = repo.get_interpretation(found.id or "", lang_norm, "concise", use_llm)
    if cached:
        return cached
    if use_llm and settings.google_api_key:
        interp = interpret_with_llm(found, lang_norm, settings.google_api_key)
    else:
        interp = interpret_local(found, lang_norm)
    repo.save_interpretation(interp, lang_norm, "concise", use_llm)
    return interp


def _maybe_attach_details(repo, found: ReadingResponse, lang_norm: str, use_llm: bool, items: list[CardWithContext]) -> None:
    if not use_llm or not settings.google_api_key:
        return
    cached_details = repo.get_details(found.id or "", lang_norm, True)
    details = cached_details if cached_details else explain_cards_with_llm(found, lang_norm, settings.google_api_key)
    if not cached_details:
        repo.save_details(found.id or "", lang_norm, True, details)
    for i, d in enumerate(details):
        if i < len(items):
            items[i].llm_detail = d


@router.post("/", response_model=ReadingResponse, dependencies=[Depends(require_api_auth)])
@router.post("", response_model=ReadingResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def reading(request: Request, payload: ReadingRequest | None = None):
    deck = get_deck_loader(request)
    repo = get_reading_repo(request)
    # FastAPI가 자동으로 JSON body를 ReadingRequest로 파싱
    assert payload is not None
    items_raw = create_reading(
        deck.cards,
        order=[g.value for g in payload.group_order],
        shuffle_times=payload.shuffle_times,
        seed=payload.seed,
        allow_reversed=payload.allow_reversed,
    )
    items = [DrawnCard(position=i["position"], is_reversed=i["is_reversed"], card=Card(**i["card"])) for i in items_raw]
    resp = ReadingResponse(question=payload.question, order=payload.group_order, count=len(items), items=items)
    repo.create(resp)
    return resp


@router.get("/{reading_id}", response_model=ReadingResponse)
@limiter.limit(settings.rate_limit_cards)
def get_reading(request: Request, reading_id: str):
    repo = get_reading_repo(request)
    found = repo.get(reading_id)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    return found


@router.post("/{reading_id}/interpret", response_model=InterpretResponse, dependencies=[Depends(require_api_auth)])
@router.post("/{reading_id}/interpret/", response_model=InterpretResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def interpret_reading(request: Request, reading_id: str, payload: InterpretRequest):
    repo = get_reading_repo(request)
    found = repo.get(reading_id)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    use_llm = payload.use_llm and bool(settings.google_api_key)
    api_key = settings.google_api_key if use_llm else None
    # normalize language for caching (auto -> detected)
    requested_lang = payload.lang
    lang_norm = detect_lang(found.question) if requested_lang == "auto" else requested_lang
    # cache check
    cached = repo.get_interpretation(reading_id, lang_norm, payload.style, use_llm)
    if cached:
        return cached
    # compute
    result = interpret_with_llm(found, lang_norm, api_key) if use_llm else interpret_local(found, lang_norm)
    # save cache
    repo.save_interpretation(result, lang_norm, payload.style, use_llm)
    return result


@router.get("/{reading_id}/result", response_model=FullReadingResult)
@router.get("/{reading_id}/result/", response_model=FullReadingResult)
@limiter.limit(settings.rate_limit_cards)
def get_full_result(request: Request, reading_id: str, lang: str = "ko", use_llm: bool = False):
    repo = get_reading_repo(request)
    deck = get_deck_loader(request)
    found = repo.get(reading_id)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    # normalize language once (auto -> detected)
    lang_norm = detect_lang(found.question) if lang == "auto" else lang
    items = _build_items_with_context(found, deck, lang_norm)
    interp = _load_or_compute_interpretation(repo, found, lang_norm, use_llm)
    _maybe_attach_details(repo, found, lang_norm, use_llm, items)
    return FullReadingResult(id=found.id or "", question=found.question, lang=lang_norm, items=items, summary=interp.summary, advices=interp.advices, llm_used=interp.llm_used, sections=getattr(interp, "sections", None))


@router.get("/daily", response_model=DailyFortuneResponse)
@router.get("/daily/", response_model=DailyFortuneResponse)
@limiter.limit(settings.rate_limit_cards)
def daily_fortune(request: Request, lang: str = "auto", seed: int | None = None, use_llm: bool = False):
    deck = get_deck_loader(request)
    # 오늘 날짜 고정 + 선택적 시드로 재현 가능
    today = datetime.now(timezone.utc).date().isoformat()
    rng = random.Random(seed)
    cards = deck.cards
    if not cards:
        raise HTTPException(status_code=500, detail="deck not loaded")
    # 한 장 뽑기
    picked = rng.choice(cards)
    is_reversed = bool(rng.randint(0, 1))
    # 언어 정규화
    q = "오늘의 총운"
    lang_norm = detect_lang(q) if lang == "auto" else lang
    # 역할/의미 구성
    roles_ko = {1: "이슈"}
    roles_en = {1: "Issue"}
    roles_ja = {1: "課題"}
    roles_zh = {1: "议题"}
    lang_key = (lang_norm or "en").lower()
    role_map = roles_zh if lang_key.startswith("zh") else roles_ko if lang_key == "ko" else roles_ja if lang_key == "ja" else roles_en
    m = deck.get_meanings(int(picked.get("id")), lang_norm, is_reversed)
    card_ctx = CardWithContext(
        position=1,
        role=role_map.get(1, ""),
        is_reversed=is_reversed,
        used_meanings=(m[:3] if m else None),
        card=Card(**picked),
    )
    # 요약: LLM 사용 여부에 따라 분기
    dummy_reading = ReadingResponse(id="", question=q, order=[], count=1, items=[DrawnCard(position=1, is_reversed=is_reversed, card=Card(**picked))])
    if use_llm and settings.google_api_key:
        interp = interpret_with_llm(dummy_reading, lang_norm, settings.google_api_key)
    else:
        interp = interpret_local(dummy_reading, lang_norm)
    return DailyFortuneResponse(date=today, lang=lang_norm, card=card_ctx, summary=interp.summary, llm_used=interp.llm_used)


@router.get("/spreads", response_model=SpreadsResponse)
@limiter.limit(settings.rate_limit_cards)
def list_spreads(request: Request):
    # 기본 8장 스프레드와 1장(오늘의 운세)
    items = [
        SpreadInfo(code="daily", name="Daily One Card", positions={1: "Issue"}).model_dump(),
        SpreadInfo(code="8-basic", name="Eight Positions", positions={1: "Issue", 2: "Hidden Influence", 3: "Past", 4: "Present", 5: "Near Future", 6: "Inner", 7: "Outer", 8: "Solution"}).model_dump(),
    ]
    return JSONResponse(content={"items": items})

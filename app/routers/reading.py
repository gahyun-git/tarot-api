import os
from fastapi import APIRouter, Depends, Request, HTTPException
from app.core.deps import get_deck_loader, get_reading_repo
from app.schemas.reading import (
    ReadingRequest,
    ReadingResponse,
    DrawnCard,
    InterpretRequest,
    InterpretResponse,
    FullReadingResult,
    CardWithContext,
)
from app.schemas.cards import Card
from app.services.reading_service import create_reading
from app.core.rate_limit import limiter
from app.core.config import settings
from app.services.interpret_service import interpret_local, interpret_with_llm, detect_lang, explain_cards_with_llm
from app.core.security import require_api_auth

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/", response_model=ReadingResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def reading(request: Request, deck = Depends(get_deck_loader), repo = Depends(get_reading_repo), payload: ReadingRequest | None = None):
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
def get_reading(request: Request, reading_id: str, repo = Depends(get_reading_repo)):
    found = repo.get(reading_id)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    return found


@router.post("/{reading_id}/interpret", response_model=InterpretResponse, dependencies=[Depends(require_api_auth)])
@limiter.limit(settings.rate_limit_reading_post)
def interpret_reading(request: Request, reading_id: str, payload: InterpretRequest, repo = Depends(get_reading_repo)):
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
@limiter.limit(settings.rate_limit_cards)
def get_full_result(request: Request, reading_id: str, lang: str = "ko", use_llm: bool = False, repo = Depends(get_reading_repo)):
    found = repo.get(reading_id)
    if not found:
        raise HTTPException(status_code=404, detail="reading not found")
    # compose card contexts
    pos_role = {1: "이슈", 2: "숨은 영향", 3: "과거", 4: "현재", 5: "근미래", 6: "내면", 7: "외부", 8: "솔루션"}
    items: list[CardWithContext] = []
    for it in found.items:
        m = it.card.upright_meaning if not it.is_reversed else it.card.reversed_meaning
        items.append(CardWithContext(position=it.position, role=pos_role.get(it.position, ""), is_reversed=it.is_reversed, used_meanings=(m[:3] if m else None), card=it.card))
    # interpretation
    # normalize language for caching (auto -> detected)
    lang_norm = detect_lang(found.question) if lang == "auto" else lang
    # load or compute interpretation (cache aware)
    cached = repo.get_interpretation(reading_id, lang_norm, "concise", use_llm)
    if cached:
        interp = cached
    else:
        if use_llm and settings.google_api_key:
            interp = interpret_with_llm(found, lang_norm, settings.google_api_key)
        else:
            interp = interpret_local(found, lang_norm)
        repo.save_interpretation(interp, lang_norm, "concise", use_llm)
    # 카드별 상세 해설(옵션: LLM)
    if use_llm and settings.google_api_key:
        details = explain_cards_with_llm(found, lang_norm, settings.google_api_key)
        for i, d in enumerate(details):
            if i < len(items):
                items[i].llm_detail = d
    return FullReadingResult(id=found.id or "", question=found.question, lang=lang_norm, items=items, summary=interp.summary, advices=interp.advices, llm_used=interp.llm_used, sections=getattr(interp, "sections", None))

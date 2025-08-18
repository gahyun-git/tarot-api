from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.core.config import settings
from app.core.deps import get_deck_loader
from app.core.rate_limit import limiter
from app.schemas.cards import Card, CardMeaningsResponse, CardsResponse

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/", response_model=CardsResponse)
@limiter.limit(settings.rate_limit_cards)
def list_cards(request: Request):
    deck = get_deck_loader(request)
    # ETag handling
    etag = getattr(deck, "etag", None)
    inm = request.headers.get("if-none-match")
    if etag and inm == etag:
        return Response(status_code=304)
    items = [Card(**c).model_dump() for c in deck.cards]
    resp = JSONResponse(content={"total": len(items), "items": items})
    if etag:
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@router.get("/{card_id}", response_model=Card)
@limiter.limit(settings.rate_limit_cards)
def get_card(request: Request, card_id: int):
    deck = get_deck_loader(request)
    for c in deck.cards:
        if c.get("id") == card_id:
            return Card(**c)
    raise HTTPException(status_code=404, detail="card not found")


@router.get("/{card_id}/meanings", response_model=CardMeaningsResponse)
@limiter.limit(settings.rate_limit_cards)
def get_card_meanings(request: Request, card_id: int, lang: str = "auto"):
    deck = get_deck_loader(request)
    # 언어 정규화: 카드 이름으로는 감지하기 어려워 기본 ko
    lang_norm = "ko" if lang == "auto" else lang
    # 카드 존재 확인
    target = None
    for c in deck.cards:
        if c.get("id") == card_id:
            target = c
            break
    if target is None:
        raise HTTPException(status_code=404, detail="card not found")
    up = deck.get_meanings(card_id, lang_norm, False) or []
    rv = deck.get_meanings(card_id, lang_norm, True) or []
    return CardMeaningsResponse(id=card_id, lang=lang_norm, upright=up, reversed=rv)

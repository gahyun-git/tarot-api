from fastapi import APIRouter, Depends, Request, HTTPException
from app.core.deps import get_deck_loader
from app.schemas.cards import CardsResponse, Card
from app.core.rate_limit import limiter
from app.core.config import settings

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/", response_model=CardsResponse)
@limiter.limit(settings.rate_limit_cards)
def list_cards(request: Request, deck = Depends(get_deck_loader)):
    # ETag handling
    etag = getattr(deck, "etag", None)
    inm = request.headers.get("if-none-match")
    if etag and inm == etag:
        from starlette.responses import Response
        return Response(status_code=304)
    items = [Card(**c).model_dump() for c in deck.cards]
    from fastapi.responses import JSONResponse
    resp = JSONResponse(content={"total": len(items), "items": items})
    if etag:
        resp.headers["ETag"] = etag
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@router.get("/{card_id}", response_model=Card)
@limiter.limit(settings.rate_limit_cards)
def get_card(request: Request, card_id: int, deck = Depends(get_deck_loader)):
    for c in deck.cards:
        if c.get("id") == card_id:
            return Card(**c)
    raise HTTPException(status_code=404, detail="card not found")

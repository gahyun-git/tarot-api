from fastapi import APIRouter, Depends
from app.core.deps import get_deck_loader
from app.schemas.cards import CardsResponse, Card

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/", response_model=CardsResponse)
def list_cards(deck = Depends(get_deck_loader)):
    items = [Card(**c) for c in deck.cards]
    return {"total": len(items), "items": items}

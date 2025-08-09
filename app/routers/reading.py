from fastapi import APIRouter, Depends
from app.core.deps import get_deck_loader
from app.schemas.reading import ReadingRequest, ReadingResponse, DrawnCard
from app.schemas.cards import Card
from app.services.reading_service import create_reading

router = APIRouter(prefix="/reading", tags=["reading"])


@router.post("/", response_model=ReadingResponse)
def reading(deck = Depends(get_deck_loader), payload: ReadingRequest | None = None):
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
    return ReadingResponse(question=payload.question, order=payload.group_order, count=len(items), items=items)

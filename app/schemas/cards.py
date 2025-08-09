from pydantic import BaseModel
from typing import Optional


class Card(BaseModel):
    id: int
    name: str
    arcana: str
    suit: Optional[str] = None
    image_url: Optional[str] = None
    upright_meaning: Optional[str] = None
    reversed_meaning: Optional[str] = None


class CardsResponse(BaseModel):
    total: int
    items: list[Card]

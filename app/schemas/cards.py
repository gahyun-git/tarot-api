from typing import Optional

from pydantic import BaseModel


class Card(BaseModel):
    id: int
    name: str
    arcana: str
    suit: Optional[str] = None
    image_url: Optional[str] = None
    upright_meaning: Optional[list[str]] = None
    reversed_meaning: Optional[list[str]] = None


class CardsResponse(BaseModel):
    total: int
    items: list[Card]


class CardMeaningsResponse(BaseModel):
    id: int
    lang: str
    upright: list[str]
    reversed: list[str]

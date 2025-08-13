from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.cards import Card


class GroupOrder(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class ReadingRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    group_order: List[GroupOrder] = Field(
        description="세 그룹을 사용자가 선택한 순서대로 예: [A,B,C]",
        min_length=3,
        max_length=3,
    )
    shuffle_times: int = Field(default=1, ge=1, le=50)
    seed: Optional[int] = Field(default=None)
    allow_reversed: bool = Field(default=True)

    @field_validator("group_order")
    @classmethod
    def validate_group_order_unique(cls, v: List[GroupOrder]) -> List[GroupOrder]:
        if len(set(v)) != 3:
            raise ValueError("group_order는 A,B,C를 한 번씩 포함해야 합니다")
        return v


class DrawnCard(BaseModel):
    position: int
    is_reversed: bool
    card: Card


class ReadingResponse(BaseModel):
    id: Optional[str] = None
    question: str
    order: List[GroupOrder]
    count: int
    items: list[DrawnCard]


class InterpretRequest(BaseModel):
    lang: str = Field(default="ko", pattern="^(ko|en|ja|zh|auto)$")
    style: str = Field(default="concise")
    use_llm: bool = Field(default=False)


class InterpretResponse(BaseModel):
    id: str
    lang: str
    summary: str
    positions: list[str]
    advices: list[str]
    llm_used: bool
    sections: Optional[dict[str, dict[str, str]]] = None  # { role: { card, orientation, analysis } }


class CardWithContext(BaseModel):
    position: int
    role: str
    is_reversed: bool
    used_meanings: Optional[List[str]] = None
    card: Card
    llm_detail: Optional[str] = None


class FullReadingResult(BaseModel):
    id: str
    question: str
    lang: str
    items: list[CardWithContext]
    summary: str
    advices: list[str]
    llm_used: bool
    sections: Optional[dict[str, dict[str, str]]] = None

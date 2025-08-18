import random as _random
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone

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
)
from app.services.interpret_service import (
    detect_lang,
    explain_cards_with_llm,
    interpret_local,
    interpret_with_llm,
)
from app.services.reading_service import create_reading as core_create_reading


def _role_map_for_lang(lang_norm: str) -> dict[int, str]:
    roles_ko = {
        1: "이슈",
        2: "숨은 영향",
        3: "과거",
        4: "현재",
        5: "근미래",
        6: "내면",
        7: "외부",
        8: "솔루션",
    }
    roles_en = {
        1: "Issue",
        2: "Hidden Influence",
        3: "Past",
        4: "Present",
        5: "Near Future",
        6: "Inner",
        7: "Outer",
        8: "Solution",
    }
    roles_ja = {
        1: "課題",
        2: "潜在的影響",
        3: "過去",
        4: "現在",
        5: "近未来",
        6: "内面",
        7: "外部",
        8: "ソリューション",
    }
    roles_zh = {
        1: "议题",
        2: "潜在影响",
        3: "过去",
        4: "现在",
        5: "近未来",
        6: "内在",
        7: "外在",
        8: "解决方案",
    }
    lang_key = (lang_norm or "en").lower()
    if lang_key.startswith("zh"):
        return roles_zh
    if lang_key == "ko":
        return roles_ko
    if lang_key == "ja":
        return roles_ja
    return roles_en


def _build_items_with_context(
    found: ReadingResponse, deck, lang_norm: str
) -> list[CardWithContext]:
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


def _load_or_compute_interpretation(
    repo, found: ReadingResponse, lang_norm: str, use_llm: bool, api_key: str | None
) -> InterpretResponse:
    cached = repo.get_interpretation(found.id or "", lang_norm, "concise", use_llm)
    if cached:
        return cached
    if use_llm and api_key:
        interp = interpret_with_llm(found, lang_norm, api_key)
    else:
        interp = interpret_local(found, lang_norm)
    repo.save_interpretation(interp, lang_norm, "concise", use_llm)
    return interp


@dataclass
class ResultContext:
    repo: object
    reading: ReadingResponse
    lang_norm: str
    api_key: str | None
    use_llm: bool


def _maybe_attach_details(ctx: ResultContext, items: list[CardWithContext]) -> None:
    if not ctx.use_llm or not ctx.api_key:
        return
    cached_details = ctx.repo.get_details(ctx.reading.id or "", ctx.lang_norm, True)
    details = (
        cached_details
        if cached_details
        else explain_cards_with_llm(ctx.reading, ctx.lang_norm, ctx.api_key)
    )
    if not cached_details:
        ctx.repo.save_details(ctx.reading.id or "", ctx.lang_norm, True, details)
    for i, d in enumerate(details):
        if i < len(items):
            items[i].llm_detail = d


def create_and_save_reading(repo, deck, payload: ReadingRequest) -> ReadingResponse:
    items_raw = core_create_reading(
        deck.cards,
        order=[g.value for g in payload.group_order],
        shuffle_times=payload.shuffle_times,
        seed=payload.seed,
        allow_reversed=payload.allow_reversed,
    )
    items = [
        DrawnCard(position=i["position"], is_reversed=i["is_reversed"], card=Card(**i["card"]))
        for i in items_raw
    ]
    resp = ReadingResponse(
        question=payload.question, order=payload.group_order, count=len(items), items=items
    )
    repo.create(resp)
    # create share slug for convenience
    if hasattr(repo, "create_share_slug"):
        with suppress(Exception):
            repo.create_share_slug(resp.id or "")
    return resp


@dataclass
class FullResultParams:
    repo: object
    deck: object
    reading_id: str
    lang: str
    use_llm: bool
    api_key: str | None


def get_full_result(params: FullResultParams) -> FullReadingResult:
    repo = params.repo
    deck = params.deck
    reading_id = params.reading_id
    lang = params.lang
    use_llm = params.use_llm
    api_key = params.api_key
    found = repo.get(reading_id)
    if not found:
        raise ValueError("reading not found")
    lang_norm = detect_lang(found.question) if lang == "auto" else lang
    items = _build_items_with_context(found, deck, lang_norm)
    interp = _load_or_compute_interpretation(repo, found, lang_norm, use_llm, api_key)
    _maybe_attach_details(ResultContext(repo, found, lang_norm, api_key, use_llm), items)
    return FullReadingResult(
        id=found.id or "",
        question=found.question,
        lang=lang_norm,
        items=items,
        summary=interp.summary,
        advices=interp.advices,
        llm_used=interp.llm_used,
        sections=getattr(interp, "sections", None),
    )


def interpret_and_cache(
    repo, reading_id: str, payload: InterpretRequest, api_key: str | None
) -> InterpretResponse:
    found = repo.get(reading_id)
    if not found:
        raise ValueError("reading not found")
    use_llm = payload.use_llm and bool(api_key)
    requested_lang = payload.lang
    lang_norm = detect_lang(found.question) if requested_lang == "auto" else requested_lang
    cached = repo.get_interpretation(reading_id, lang_norm, payload.style, use_llm)
    if cached:
        return cached
    result = (
        interpret_with_llm(found, lang_norm, api_key)
        if use_llm
        else interpret_local(found, lang_norm)
    )
    repo.save_interpretation(result, lang_norm, payload.style, use_llm)
    return result


def daily_fortune_result(
    deck, lang: str, seed: int | None, use_llm: bool, api_key: str | None
) -> DailyFortuneResponse:
    today = datetime.now(timezone.utc).date().isoformat()
    rng = _random.Random(seed)
    cards = deck.cards
    if not cards:
        raise RuntimeError("deck not loaded")
    picked = cards[rng.randrange(len(cards))]
    is_reversed = bool(rng.randint(0, 1))
    q = "오늘의 총운"
    lang_norm = detect_lang(q) if lang == "auto" else lang
    role_map = _role_map_for_lang(lang_norm)
    m = deck.get_meanings(int(picked.get("id")), lang_norm, is_reversed)
    card_ctx = CardWithContext(
        position=1,
        role=role_map.get(1, ""),
        is_reversed=is_reversed,
        used_meanings=(m[:3] if m else None),
        card=Card(**picked),
    )
    dummy_reading = ReadingResponse(
        id="",
        question=q,
        order=[],
        count=1,
        items=[DrawnCard(position=1, is_reversed=is_reversed, card=Card(**picked))],
    )
    interp = (
        interpret_with_llm(dummy_reading, lang_norm, api_key)
        if (use_llm and api_key)
        else interpret_local(dummy_reading, lang_norm)
    )
    return DailyFortuneResponse(
        date=today, lang=lang_norm, card=card_ctx, summary=interp.summary, llm_used=interp.llm_used
    )

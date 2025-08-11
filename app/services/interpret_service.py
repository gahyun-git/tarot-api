from __future__ import annotations

from typing import List
import json

from app.schemas.reading import ReadingResponse, InterpretResponse
import re

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


POS_TEXT_KO = {
    1: "이슈",
    2: "숨은 영향",
    3: "과거",
    4: "현재",
    5: "근미래",
    6: "내면",
    7: "외부",
    8: "솔루션",
}


def _lines_and_advices(reading: ReadingResponse, lang: str) -> tuple[List[str], List[str], str]:
    pos_text = POS_TEXT_KO  # TODO: en/ja 사전 추가 가능
    lines: List[str] = []
    advices: List[str] = []
    for it in reading.items:
        card = it.card
        meanings = card.upright_meaning if not it.is_reversed else card.reversed_meaning
        top = ", ".join((meanings or [])[:2]) if meanings else ""
        orient = "정" if not it.is_reversed else "역"
        lines.append(f"{it.position}. {pos_text.get(it.position, '')}: {card.name} ({orient}) - {top}")
        if it.position == 8 and meanings:
            advices.append(f"솔루션: {meanings[0]}을(를) 오늘 작은 실행으로 시작하세요.")
    for it in reading.items:
        if len(advices) >= 3:
            break
        meanings = it.card.upright_meaning if not it.is_reversed else it.card.reversed_meaning
        if meanings:
            advices.append(f"보조: {meanings[0]} 관점에서 한 가지 실험을 추가하세요.")
    summary = (
        "흐름 요약: 8번 솔루션을 중심으로 현재 상황과 내외부 요인을 연결해 작게 시작하고, 반복적으로 보완하세요. 단정하지 말고 가설로 접근하세요."
    )
    return lines, advices[:3], summary


def interpret_local(reading: ReadingResponse, lang: str) -> InterpretResponse:
    lines, advices, summary = _lines_and_advices(reading, lang)
    return InterpretResponse(
        id=reading.id or "",
        lang=lang,
        summary=summary,
        positions=lines,
        advices=advices,
        llm_used=False,
    )


def detect_lang(text: str) -> str:
    if not text:
        return "ko"
    # naive heuristic
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[A-Za-z]", text) and not re.search(r"[\uac00-\ud7af]", text):
        return "en"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    return "en"


def interpret_with_llm(reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash") -> InterpretResponse:
    if lang == "auto":
        lang = detect_lang(reading.question)
    lines, advices, summary = _lines_and_advices(reading, lang)
    # 카드 컨텍스트(반드시 이 8장만 기반으로 해석하도록 전달)
    pos_text = POS_TEXT_KO
    cards_ctx = []
    for it in reading.items:
        cards_ctx.append({
            "position": it.position,
            "role": pos_text.get(it.position, ""),
            "name": it.card.name,
            "arcana": it.card.arcana,
            "is_reversed": it.is_reversed,
            "meanings": (it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning) or [],
        })
    draft = {
        "question": reading.question,
        "positions": lines,
        "advices": advices,
        "cards": cards_ctx,
        "guidelines": [
            "8번 솔루션 중심으로 연결",
            "단정 금지, 가설/제안 어조",
            "행동 조언 3개",
        ],
    }
    if genai is None:
        return interpret_local(reading, lang)
    genai.configure(api_key=api_key)
    # Persona + strict JSON schema, 카드 기반 해석 강제 + 질문 반영/섹션 형식 출력
    prompt = (
        f"You are a tarot master with 30 years of experience. Respond in language: {lang}.\n"
        f"Use compassionate yet piercing insight. Avoid deterministic claims and avoid medical/legal/financial guidance.\n"
        f"IMPORTANT: Base ALL interpretation ONLY on the following 8 cards (names/roles/orientation/meanings). Do NOT invent other cards.\n"
        f"Produce STRICT JSON (minified, no comments, no extra text).\n"
        f"Schema: {{\"summary\": string, \"sections\": {{\"현재\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, \"과거\": {{...}}, \"근미래\": {{...}}, \"내면\": {{...}}, \"외부\": {{...}}, \"이슈\": {{...}} }}, \"advices\": [{{\"type\":\"solution\"|\"support\", \"text\": string}}, {{...}}, {{...}}] }}\n"
        f"Rules:\n"
        f"1) Address the user's question first: '{reading.question}'.\n"
        f"2) Summary: 5-7 sentences; do NOT include [pos#] citations; write naturally; ground in cards.\n"
        f"3) Fill sections mapping roles(이슈, 과거, 현재, 근미래, 내면, 외부) to card name/orientation and a short analysis tailored to the question.\n"
        f"4) Exactly 3 advices: first is type=solution and must synthesize the cards with the question; the other two are type=support. Each advice short, actionable, concrete.\n"
        f"5) Ground every statement in the provided card meanings; do not invent other cards.\n"
        f"Draft: {json.dumps(draft, ensure_ascii=False)}\n"
        f"Return ONLY the JSON object."
    )
    # Guardrails: model params
    model_obj = genai.GenerativeModel(model)
    rsp = model_obj.generate_content(prompt)
    text = (rsp.text or "").strip()
    if not text:
        return interpret_local(reading, lang)
    # Try JSON parse first
    parsed_summary = None
    parsed_advices: List[str] | None = None
    parsed_sections = None
    try:
        # Extract the first JSON object (some models may add stray tokens)
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "summary" in obj and "advices" in obj:
                parsed_summary = str(obj["summary"]).strip()
                adv_list = obj.get("advices") or []
                if isinstance(adv_list, list):
                    parsed_advices = []
                    for a in adv_list:
                        if isinstance(a, dict):
                            parsed_advices.append(str(a.get("text", "")).strip())
                        else:
                            parsed_advices.append(str(a))
                    # ensure exactly 3
                    parsed_advices = parsed_advices[:3]
                parsed_sections = obj.get("sections")
    except Exception:
        parsed_summary = None
        parsed_advices = None

    if parsed_summary and parsed_advices and len(parsed_advices) == 3:
        return InterpretResponse(
            id=reading.id or "",
            lang=lang,
            summary=parsed_summary,
            positions=lines,
            advices=parsed_advices,
            llm_used=True,
            sections=parsed_sections if isinstance(parsed_sections, dict) else None,
        )

    # Fallback: bullet heuristic
    adv = advices
    if "- " in text:
        parts = [ln.strip("- ") for ln in text.splitlines() if ln.strip().startswith("-")]
        if len(parts) >= 3:
            adv = parts[:3]
    return InterpretResponse(
        id=reading.id or "",
        lang=lang,
        summary=text,
        positions=lines,
        advices=adv,
        llm_used=True,
        sections=None,
    )


def explain_cards_with_llm(reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash") -> list[str]:
    if genai is None:
        return [""] * len(reading.items)
    genai.configure(api_key=api_key)
    pos_text = POS_TEXT_KO
    cards_ctx = []
    for it in reading.items:
        cards_ctx.append({
            "role": pos_text.get(it.position, ""),
            "name": it.card.name,
            "orientation": ("reversed" if it.is_reversed else "upright"),
            "meanings": (it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning) or [],
        })
    prompt = (
        f"You are a tarot master with 30 years of experience. Respond in language: {lang}.\n"
        f"For each card below, write a 2-3 sentence analysis tailored to the user's question: '{reading.question}'.\n"
        f"Grounded in meanings and the role, avoid determinism. Return STRICT JSON array of strings, length={len(cards_ctx)}.\n"
        f"Cards: {json.dumps(cards_ctx, ensure_ascii=False)}"
    )
    model_obj = genai.GenerativeModel(model)
    rsp = model_obj.generate_content(prompt)
    t = (rsp.text or "").strip()
    try:
        m = re.search(r"\[[\s\S]*\]", t)
        if m:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x) for x in arr]
    except Exception:
        pass
    return [""] * len(cards_ctx)



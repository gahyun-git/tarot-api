from __future__ import annotations

import json
import re

from app.schemas.reading import InterpretResponse, ReadingResponse

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

# --- Sanitization helpers ----------------------------------------------------

def _sanitize_text(text: str, reading: ReadingResponse) -> str:
    """Remove card names and orientation tokens from plain text to improve readability."""
    if not text:
        return text
    try:
        # 1) remove card names (longer first to avoid partial overlaps)
        names = [str(it.card.name or "").strip() for it in getattr(reading, "items", [])]
        names = [n for n in names if n]
        if names:
            names.sort(key=len, reverse=True)
            pattern = re.compile(r"(?:" + "|".join(re.escape(n) for n in names) + r")")
            text = pattern.sub("", text)
        # 2) remove common orientation markers
        #   (정/역, upright/reversed, 正/逆/正位/逆位) + parentheses if only those tokens
        text = re.sub(r"\((?:정|역|upright|reversed|正|逆|正位|逆位)\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:정|역|upright|reversed|正|逆|正位|逆位)\b", "", text, flags=re.IGNORECASE)
        # 3) collapse excessive spaces
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text
    except Exception:
        return text

POS_TEXT_EN = {
    1: "Issue",
    2: "Hidden Influence",
    3: "Past",
    4: "Present",
    5: "Near Future",
    6: "Inner",
    7: "Outer",
    8: "Solution",
}

POS_TEXT_JA = {
    1: "課題",
    2: "潜在的影響",
    3: "過去",
    4: "現在",
    5: "近未来",
    6: "内面",
    7: "外部",
    8: "ソリューション",
}

POS_TEXT_ZH = {
    1: "议题",
    2: "潜在影响",
    3: "过去",
    4: "现在",
    5: "近未来",
    6: "内在",
    7: "外在",
    8: "解决方案",
}


EXPECTED_ADVICES = 3
SOLUTION_POSITION = 8


def _pos_text_for_lkey(lkey: str) -> dict[int, str]:
    if lkey.startswith("zh"):
        return POS_TEXT_ZH
    if lkey == "ja":
        return POS_TEXT_JA
    if lkey == "ko":
        return POS_TEXT_KO
    return POS_TEXT_EN


def _cards_context(reading: ReadingResponse, pos_map: dict[int, str]) -> list[dict[str, object]]:
    return [
        {
            "position": it.position,
            "role": pos_map.get(it.position, ""),
            "name": it.card.name,
            "arcana": it.card.arcana,
            "is_reversed": it.is_reversed,
            "meanings": (it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning)
            or [],
        }
        for it in reading.items
    ]


def _schema_for_lkey(lkey: str) -> tuple[list[str], list[str]]:
    sections_keys = {
        "ko": ["현재", "과거", "근미래", "내면", "외부", "이슈"],
        "en": ["Present", "Past", "Near Future", "Inner", "Outer", "Issue"],
        "ja": ["現在", "過去", "近未来", "内面", "外部", "課題"],
        "zh": ["现在", "过去", "近未来", "内在", "外在", "议题"],
    }
    orient = {
        "ko": ["정", "역"],
        "en": ["upright", "reversed"],
        "ja": ["正", "逆"],
        "zh": ["正位", "逆位"],
    }
    lang_map = "zh" if lkey.startswith("zh") else (lkey if lkey in {"ko", "en", "ja"} else "en")
    return sections_keys[lang_map], orient[lang_map]


def _schema_sections_str(sec: list[str]) -> str:
    return ", ".join(
        [f'"{s}": {{"card": string, "orientation": string, "analysis": string}}' for s in sec]
    )


def _build_prompt(
    lang: str, question: str, schema_sections: str, ori: list[str], draft: dict
) -> str:
    return (
        f"You are a tarot master with 30 years of experience. Respond in language: {lang}.\n"
        f"Use compassionate yet piercing insight. Avoid deterministic claims and avoid medical/legal/financial guidance.\n"
        f"IMPORTANT: Base ALL interpretation ONLY on the following 8 cards (names/roles/orientation/meanings). Do NOT invent other cards.\n"
        f"Produce STRICT JSON (minified, no comments, no extra text).\n"
        f'Schema: {{"summary": string, "sections": {{{schema_sections}}}, "advices": [{{"type":"solution"|"support", "text": string}}, {{...}}, {{...}}] }}\n'
        f"Rules:\n"
        f"1) Address the user's question first: '{question}'.\n"
        f"2) Summary: 5-7 sentences; natural prose; no [pos#] citations; explicitly connect key cards and roles.\n"
        f"3) Use orientation values strictly from this set: ['{ori[0]}','{ori[1]}'].\n"
        f"4) Exactly 3 advices: the first is type=solution (core synthesis), the other two are type=support.\n"
        f"5) Each advice must be rich and grounded: about six sentences (5–6), including (a) insight/why grounded in specific cards & roles, (b) concrete action/what to do, (c) today's first step/how to start now.\n"
        f"6) Avoid platitudes; prefer measurable, time-bounded phrasing (e.g., within 24 hours, for 7 days). Keep it compassionate but laser-focused.\n"
        f"7) Ground every statement in the provided card meanings; do not invent other cards.\n"
        f"Draft: {json.dumps(draft, ensure_ascii=False)}\n"
        f"Return ONLY the JSON object."
    )


def _call_llm(model: str, prompt: str) -> str:
    try:
        model_obj = genai.GenerativeModel(model)
        rsp = model_obj.generate_content(prompt)
        return (rsp.text or "").strip()
    except Exception:
        return ""


def _parse_output(text: str) -> tuple[str | None, list[str] | None, dict | None]:
    try:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None, None, None
        obj = json.loads(m.group(0))
        if not (isinstance(obj, dict) and "summary" in obj and "advices" in obj):
            return None, None, None
        summary = str(obj["summary"]).strip()
        adv_list = obj.get("advices") or []
        advices = (
            [str(a.get("text", "")).strip() if isinstance(a, dict) else str(a) for a in adv_list][
                :EXPECTED_ADVICES
            ]
            if isinstance(adv_list, list)
            else None
        )
        sections = obj.get("sections")
        return summary, advices, sections
    except Exception:
        return None, None, None


def _lines_and_advices(reading: ReadingResponse, lang: str) -> tuple[list[str], list[str], str]:
    # select language map
    lang_key = (lang or "en").lower()
    if lang_key.startswith("zh"):
        pos_text = POS_TEXT_ZH
        orient_u, orient_r = "正位", "逆位"
        sol_tmpl = '解决方案：今天用"{m}"开始一个小的行动。'
        sup_tmpl = '支持：从"{m}"的视角加入一个小实验。'
        summary_text = "流程摘要：以第8位（解决方案）为中心，将当前与内外因素相连，从小处着手并迭代。避免断言，以假设方式推进。"
    elif lang_key == "ja":
        pos_text = POS_TEXT_JA
        orient_u, orient_r = "正", "逆"
        sol_tmpl = "ソリューション: 「{m}」を小さな行動として今日始めましょう。"
        sup_tmpl = "サポート: 「{m}」の観点から小さな実験を一つ加えてください。"
        summary_text = "流れの要約: 8番(ソリューション)を中心に現在と内外の要因をつなぎ、小さく始め反復してください。断定は避け、仮説として進みましょう。"
    elif lang_key == "ko":
        pos_text = POS_TEXT_KO
        orient_u, orient_r = "정", "역"
        sol_tmpl = "솔루션: {m}을(를) 오늘 작은 실행으로 시작하세요."
        sup_tmpl = "보조: {m} 관점에서 한 가지 실험을 추가하세요."
        summary_text = "흐름 요약: 8번 솔루션을 중심으로 현재 상황과 내외부 요인을 연결해 작게 시작하고, 반복적으로 보완하세요. 단정하지 말고 가설로 접근하세요."
    else:
        pos_text = POS_TEXT_EN
        orient_u, orient_r = "upright", "reversed"
        sol_tmpl = "Solution: Start a small action today with '{m}'."
        sup_tmpl = "Support: Add one small experiment from the '{m}' perspective."
        summary_text = "Flow summary: Center on position 8 (Solution), link the present with inner/outer factors, start small and iterate. Avoid determinism; proceed as hypotheses."
    lines: list[str] = []
    advices: list[str] = []
    for it in reading.items:
        card = it.card
        meanings = card.upright_meaning if not it.is_reversed else card.reversed_meaning
        top = ", ".join((meanings or [])[:2]) if meanings else ""
        orient = orient_u if not it.is_reversed else orient_r
        lines.append(
            f"{it.position}. {pos_text.get(it.position, '')}: {card.name} ({orient}) - {top}"
        )
        if it.position == SOLUTION_POSITION and meanings:
            advices.append(sol_tmpl.format(m=meanings[0]))
    for it in reading.items:
        if len(advices) >= EXPECTED_ADVICES:
            break
        meanings = it.card.upright_meaning if not it.is_reversed else it.card.reversed_meaning
        if meanings:
            advices.append(sup_tmpl.format(m=meanings[0]))
    summary = summary_text
    return lines, advices[:EXPECTED_ADVICES], summary


def interpret_local(reading: ReadingResponse, lang: str) -> InterpretResponse:
    lines, advices, summary = _lines_and_advices(reading, lang)
    # sanitize summary/advices for readability
    summary = _sanitize_text(summary, reading)
    advices = [_sanitize_text(a, reading) for a in advices]
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
    # Chinese Han characters
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[A-Za-z]", text) and not re.search(r"[\uac00-\ud7af]", text):
        return "en"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    return "en"


def interpret_with_llm(
    reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash"
) -> InterpretResponse:
    # 항상 질문 언어에 맞춰 응답 (설정 언어 무시)
    lang = detect_lang(reading.question)
    lines, advices, _ = _lines_and_advices(reading, lang)
    lkey = (lang or "en").lower()
    draft = {
        "question": reading.question,
        "positions": lines,
        "advices": advices,
        "cards": _cards_context(reading, _pos_text_for_lkey(lkey)),
        "guidelines": ["8번 솔루션 중심으로 연결", "단정 금지, 가설/제안 어조", "행동 조언 3개"],
    }
    if genai is None:
        return interpret_local(reading, lang)
    genai.configure(api_key=api_key)
    sec, ori = _schema_for_lkey(lkey)
    prompt = _build_prompt(lang, reading.question, _schema_sections_str(sec), ori, draft)
    text = _call_llm(model, prompt)
    if not text:
        return interpret_local(reading, lang)
    parsed_summary, parsed_advices, parsed_sections = _parse_output(text)
    if parsed_summary and parsed_advices and len(parsed_advices) == EXPECTED_ADVICES:
        parsed_summary = _sanitize_text(parsed_summary, reading)
        parsed_advices = [_sanitize_text(a, reading) for a in parsed_advices]
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
        if len(parts) >= EXPECTED_ADVICES:
            adv = parts[:EXPECTED_ADVICES]
    return InterpretResponse(
        id=reading.id or "",
        lang=lang,
        summary=text,
        positions=lines,
        advices=adv,
        llm_used=True,
        sections=None,
    )


def explain_cards_with_llm(
    reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash"
) -> list[str]:
    # 항상 질문 언어에 맞춰 응답 (설정 언어 무시)
    lang = detect_lang(reading.question)
    if genai is None:
        return [""] * len(reading.items)
    genai.configure(api_key=api_key)
    lkey = (lang or "en").lower()

    def _pos_text_for_lang(lk: str) -> dict[int, str]:
        if lk.startswith("zh"):
            return POS_TEXT_ZH
        if lk == "ja":
            return POS_TEXT_JA
        if lk == "ko":
            return POS_TEXT_KO
        return POS_TEXT_EN

    def _orientation_value(lk: str, is_reversed: bool) -> str:
        if lk == "ko":
            return "역" if is_reversed else "정"
        if lk == "ja":
            return "逆" if is_reversed else "正"
        if lk.startswith("zh"):
            return "逆位" if is_reversed else "正位"
        return "reversed" if is_reversed else "upright"

    pos_text = _pos_text_for_lang(lkey)
    cards_ctx = []
    for it in reading.items:
        ori_val = _orientation_value(lkey, it.is_reversed)
        cards_ctx.append(
            {
                "role": pos_text.get(it.position, ""),
                "name": it.card.name,
                "orientation": ori_val,
                "meanings": (
                    it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning
                )
                or [],
            }
        )
    prompt = (
        f"You are a tarot master with 30 years of experience. Respond in language: {lang}.\n"
        f"For each card below, write a 2-3 sentence analysis tailored to the user's question: '{reading.question}'.\n"
        f"Grounded in meanings and the role, avoid determinism. Return STRICT JSON array of strings, length={len(cards_ctx)}.\n"
        f"Cards: {json.dumps(cards_ctx, ensure_ascii=False)}"
    )
    try:
        model_obj = genai.GenerativeModel(model)
        rsp = model_obj.generate_content(prompt)
        t = (rsp.text or "").strip()
    except Exception:
        return [""] * len(cards_ctx)
    try:
        m = re.search(r"\[[\s\S]*\]", t)
        if m:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x) for x in arr]
    except Exception:
        pass
    return [""] * len(cards_ctx)

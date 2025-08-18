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


def _lines_and_advices(reading: ReadingResponse, lang: str) -> tuple[list[str], list[str], str]:
    # select language map
    lang_key = (lang or "en").lower()
    if lang_key.startswith("zh"):
        pos_text = POS_TEXT_ZH
        orient_u, orient_r = "正位", "逆位"
        sol_tmpl = "解决方案：今天用\"{m}\"开始一个小的行动。"
        sup_tmpl = "支持：从\"{m}\"的视角加入一个小实验。"
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
        summary_text = (
            "흐름 요약: 8번 솔루션을 중심으로 현재 상황과 내외부 요인을 연결해 작게 시작하고, 반복적으로 보완하세요. 단정하지 말고 가설로 접근하세요."
        )
    else:
        pos_text = POS_TEXT_EN
        orient_u, orient_r = "upright", "reversed"
        sol_tmpl = "Solution: Start a small action today with '{m}'."
        sup_tmpl = "Support: Add one small experiment from the '{m}' perspective."
        summary_text = (
            "Flow summary: Center on position 8 (Solution), link the present with inner/outer factors, start small and iterate. Avoid determinism; proceed as hypotheses."
        )
    lines: list[str] = []
    advices: list[str] = []
    for it in reading.items:
        card = it.card
        meanings = card.upright_meaning if not it.is_reversed else card.reversed_meaning
        top = ", ".join((meanings or [])[:2]) if meanings else ""
        orient = orient_u if not it.is_reversed else orient_r
        lines.append(f"{it.position}. {pos_text.get(it.position, '')}: {card.name} ({orient}) - {top}")
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


def interpret_with_llm(reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash") -> InterpretResponse:
    lang = detect_lang(reading.question) if lang == "auto" else lang
    lines, advices, summary = _lines_and_advices(reading, lang)
    lkey = (lang or "en").lower()

    def _pos_text_for_lang(lk: str) -> dict[int, str]:
        if lk.startswith("zh"):
            return POS_TEXT_ZH
        if lk == "ja":
            return POS_TEXT_JA
        if lk == "ko":
            return POS_TEXT_KO
        return POS_TEXT_EN

    pos_text = _pos_text_for_lang(lkey)

    def _cards_context() -> list[dict[str, object]]:
        ctx: list[dict[str, object]] = []
        for it in reading.items:
            ctx.append({
                "position": it.position,
                "role": pos_text.get(it.position, ""),
                "name": it.card.name,
                "arcana": it.card.arcana,
                "is_reversed": it.is_reversed,
                "meanings": (it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning) or [],
            })
        return ctx

    draft = {
        "question": reading.question,
        "positions": lines,
        "advices": advices,
        "cards": _cards_context(),
        "guidelines": [
            "8번 솔루션 중심으로 연결",
            "단정 금지, 가설/제안 어조",
            "행동 조언 3개",
        ],
    }
    if genai is None:
        return interpret_local(reading, lang)
    genai.configure(api_key=api_key)
    # Persona + strict JSON schema (언어별 섹션/오리엔테이션)
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
    sec = sections_keys[lang_map]
    ori = orient[lang_map]
    schema_sections = (
        f"\"{sec[0]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, "
        f"\"{sec[1]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, "
        f"\"{sec[2]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, "
        f"\"{sec[3]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, "
        f"\"{sec[4]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}, "
        f"\"{sec[5]}\": {{\"card\": string, \"orientation\": string, \"analysis\": string}}"
    )
    prompt = (
        f"You are a tarot master with 30 years of experience. Respond in language: {lang}.\n"
        f"Use compassionate yet piercing insight. Avoid deterministic claims and avoid medical/legal/financial guidance.\n"
        f"IMPORTANT: Base ALL interpretation ONLY on the following 8 cards (names/roles/orientation/meanings). Do NOT invent other cards.\n"
        f"Produce STRICT JSON (minified, no comments, no extra text).\n"
        f"Schema: {{\"summary\": string, \"sections\": {{{schema_sections}}}, \"advices\": [{{\"type\":\"solution\"|\"support\", \"text\": string}}, {{...}}, {{...}}] }}\n"
        f"Rules:\n"
        f"1) Address the user's question first: '{reading.question}'.\n"
        f"2) Summary: 5-7 sentences; do NOT include [pos#] citations; write naturally; ground in cards.\n"
        f"3) Use orientation values strictly from this set: ['{ori[0]}','{ori[1]}'].\n"
        f"4) Exactly 3 advices: first is type=solution and must synthesize the cards with the question; the other two are type=support. Each advice short, actionable, concrete.\n"
        f"5) Ground every statement in the provided card meanings; do not invent other cards.\n"
        f"Draft: {json.dumps(draft, ensure_ascii=False)}\n"
        f"Return ONLY the JSON object."
    )
    # Guardrails: model params
    try:
        model_obj = genai.GenerativeModel(model)
        rsp = model_obj.generate_content(prompt)
        text = (rsp.text or "").strip()
    except Exception:
        # 업스트림(LLM) 오류 시 500으로 전파하지 않고 로컬 해석으로 폴백
        return interpret_local(reading, lang)
    if not text:
        return interpret_local(reading, lang)
    # Try JSON parse first
    parsed_summary = None
    parsed_advices: list[str] | None = None
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

    if parsed_summary and parsed_advices and len(parsed_advices) == EXPECTED_ADVICES:
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


def explain_cards_with_llm(reading: ReadingResponse, lang: str, api_key: str, model: str = "gemini-1.5-flash") -> list[str]:
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
        cards_ctx.append({
            "role": pos_text.get(it.position, ""),
            "name": it.card.name,
            "orientation": ori_val,
            "meanings": (it.card.reversed_meaning if it.is_reversed else it.card.upright_meaning) or [],
        })
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



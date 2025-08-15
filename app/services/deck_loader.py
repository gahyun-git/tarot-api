import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DeckLoader:
    def __init__(self, data_path: str, meanings_path: str | None = None, prefer_local_images: bool = True):
        self._data_path = Path(data_path)
        self._meanings_path = Path(meanings_path) if meanings_path else None
        self._cards: list[dict[str, Any]] = []
        self._prefer_local = prefer_local_images
        self._etag: str | None = None
        self._meanings_by_lang: dict[str, dict[str, dict[str, list[str]]]] = {}

    @property
    def cards(self) -> list[dict[str, Any]]:
        if not self._cards:
            self.load()
        return self._cards

    def load(self) -> None:
        with self._data_path.open("r", encoding="utf-8") as f:
            self._cards = json.load(f)
        if not isinstance(self._cards, list):
            raise ValueError("Deck json must be a list")
        if len(self._cards) != 78:
            logger.warning("Deck has %d cards (expected 78)", len(self._cards))
        # Prefer local static image path if available
        if self._prefer_local:
            for c in self._cards:
                cid = c.get("id")
                local_path = Path("static/cards") / f"{cid:02d}.jpg"
                if local_path.exists():
                    c["image_url"] = f"/static/cards/{cid:02d}.jpg"
        # Merge meanings if provided
        if self._meanings_path and self._meanings_path.exists():
            try:
                with self._meanings_path.open("r", encoding="utf-8") as mf:
                    meanings = json.load(mf)
                # Expect format: { "<id>": { "upright": [...], "reversed": [...] }, ... }
                if isinstance(meanings, dict):
                    by_id: dict[str, Any] = {str(c.get("id")): c for c in self._cards}
                    merged_count = 0
                    for key, val in meanings.items():
                        card = by_id.get(str(key))
                        if card is None:
                            continue
                        if isinstance(val, dict):
                            if "upright" in val:
                                card["upright_meaning"] = val["upright"]
                            if "reversed" in val:
                                card["reversed_meaning"] = val["reversed"]
                            merged_count += 1
                    logger.info("Merged meanings for %d cards from %s", merged_count, self._meanings_path)
            except Exception:
                logger.exception("Failed to load meanings file")
        # Preload multi-language meanings maps if available
        self._meanings_by_lang = {}
        for lang_code in ("ko", "en", "ja", "zh"):
            path = None
            if lang_code == "zh":
                # no dedicated zh file by default; skip (fallback will handle)
                path = None
            else:
                candidate = Path("data") / f"meanings.{lang_code}.json"
                if candidate.exists():
                    path = candidate
            if path is None:
                continue
            try:
                with path.open("r", encoding="utf-8") as mf:
                    mobj = json.load(mf)
                if isinstance(mobj, dict):
                    lang_map: dict[str, dict[str, list[str]]] = {}
                    for key, val in mobj.items():
                        if isinstance(val, dict):
                            lang_map[str(key)] = {
                                "upright": list(val.get("upright") or []),
                                "reversed": list(val.get("reversed") or []),
                            }
                    self._meanings_by_lang[lang_code] = lang_map
                    logger.info("Loaded meanings for %s: %d cards", lang_code, len(lang_map))
            except Exception:
                logger.exception("Failed to load meanings file for %s", lang_code)
        # Compute ETag (hash of ids + optional meanings mtime)
        h = hashlib.sha1()
        ids = ",".join(str(c.get("id")) for c in self._cards)
        h.update(ids.encode())
        if self._meanings_path and self._meanings_path.exists():
            h.update(str(self._meanings_path.stat().st_mtime_ns).encode())
        self._etag = f"W/\"{h.hexdigest()}\""

    @property
    def etag(self) -> str | None:
        return self._etag

    def get_meanings(self, card_id: int, lang: str, is_reversed: bool) -> Optional[list[str]]:
        """Return meanings for a card id in requested language with sensible fallbacks.

        Fallback order: requested lang → en → ko → stored on card (if any).
        """
        key = str(card_id)
        lang_key = (lang or "").lower()
        choices = [lang_key]
        if lang_key.startswith("zh"):
            # no zh file by default, prefer en then ko
            choices = [lang_key, "en", "ko"]
        elif lang_key == "ja":
            choices = ["ja", "en", "ko"]
        elif lang_key == "ko":
            choices = ["ko", "en"]
        else:
            choices = ["en", "ko"] if lang_key == "en" else [lang_key, "en", "ko"]

        for ck in choices:
            m = self._meanings_by_lang.get(ck)
            if not m:
                continue
            obj = m.get(key)
            if not obj:
                continue
            vals = obj.get("reversed" if is_reversed else "upright")
            if vals:
                return vals
        # Fallback to embedded card meanings
        for c in self._cards:
            if c.get("id") == card_id:
                vals = c.get("reversed_meaning" if is_reversed else "upright_meaning")
                if vals:
                    return list(vals)
                break
        return None

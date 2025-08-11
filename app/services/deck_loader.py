import json
import logging
from pathlib import Path
from typing import Any, List
import hashlib

logger = logging.getLogger(__name__)


class DeckLoader:
    def __init__(self, data_path: str, meanings_path: str | None = None, prefer_local_images: bool = True):
        self._data_path = Path(data_path)
        self._meanings_path = Path(meanings_path) if meanings_path else None
        self._cards: List[dict[str, Any]] = []
        self._prefer_local = prefer_local_images
        self._etag: str | None = None

    @property
    def cards(self) -> List[dict[str, Any]]:
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

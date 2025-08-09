import json
import logging
from pathlib import Path
from typing import Any, List

logger = logging.getLogger(__name__)


class DeckLoader:
    def __init__(self, data_path: str):
        self._data_path = Path(data_path)
        self._cards: List[dict[str, Any]] = []

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

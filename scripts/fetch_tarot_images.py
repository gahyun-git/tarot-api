#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

import httpx

RAW_URL = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/tarot-images.json"
CARDS_BASE = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/cards/"
ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "tarot-images.json"

REQUIRED_KEYS = {"id", "name", "arcana"}

def fetch() -> list[dict[str, Any]]:
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        r = client.get(RAW_URL)
        r.raise_for_status()
        raw = r.json()
    # Expecting { description: str, cards: [ ... ] }
    if not isinstance(raw, dict) or "cards" not in raw or not isinstance(raw["cards"], list):
        raise ValueError("Invalid payload: expected object with 'cards' list")
    cards_raw: list[dict[str, Any]] = raw["cards"]

    mapped: list[dict[str, Any]] = []
    for idx, c in enumerate(cards_raw):
        name = c.get("name")
        arcana = c.get("arcana")
        suit = c.get("suit")
        img = c.get("img")
        image_url = f"{CARDS_BASE}{img}" if img else None
        mapped.append({
            "id": idx,
            "name": name,
            "arcana": arcana,
            "suit": suit,
            "image_url": image_url,
        })
    return mapped


EXPECTED_CARDS = 78


def validate(data: list[dict[str, Any]]) -> None:
    if len(data) < EXPECTED_CARDS:
        raise ValueError(f"Expected >=78 cards, got {len(data)}")
    ids = [c.get("id") for c in data]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate card id detected")
    for c in data:
        if not REQUIRED_KEYS.issubset(c.keys()):
            raise ValueError(f"Missing keys in card: {c}")
        if c.get("arcana") not in ("Major Arcana", "Minor Arcana"):
            raise ValueError("Invalid arcana value")


def write(data: list[dict[str, Any]]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    data = fetch()
    validate(data)
    if args.validate_only:
        print(f"OK: {len(data)} cards (validate-only)")
        return 0

    write(data)
    print(f"Updated {DATA_PATH} with {len(data)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

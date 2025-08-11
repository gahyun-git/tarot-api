#!/usr/bin/env python3
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from typing import Dict

import httpx
from PIL import Image


ARCHIVE_ITEM = "https://archive.org/metadata/rider-waite-tarot"
FILE_BASE = "https://archive.org/download/rider-waite-tarot/{}"

# Map (id -> archive filename). We infer names by suit/rank for minors.
MAJOR_NAMES = [
    "fool",
    "magician",
    "priestess",
    "empress",
    "emperor",
    "hierophant",
    "lovers",
    "chariot",
    "strength",
    "hermit",
    "fortune",
    "justice",
    "hanged",
    "death",
    "temperance",
    "devil",
    "tower",
    "star",
    "moon",
    "sun",
    "judgement",
    "world",
]

SUITS = [("wands", 50), ("cups", 22), ("swords", 36), ("pentacles", 64)]
RANKS = [
    ("ace", 0),
    ("2", 1),
    ("3", 2),
    ("4", 3),
    ("5", 4),
    ("6", 5),
    ("7", 6),
    ("8", 7),
    ("9", 8),
    ("10", 9),
    ("page", 10),
    ("knight", 11),
    ("queen", 12),
    ("king", 13),
]


def id_to_filename(cid: int) -> str:
    if 0 <= cid <= 21:
        key = MAJOR_NAMES[cid]
        return f"major_arcana_{key}.png"
    # minors
    for suit, start in SUITS:
        if start <= cid <= start + 13:
            rank_name, offset = RANKS[cid - start]
            return f"minor_arcana_{suit}_{rank_name}.png"
    raise ValueError(f"invalid card id: {cid}")


def download_and_save_png_as_jpg(url: str, dest: Path, quality: int = 85) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.save(dest, format="JPEG", quality=quality, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache 78 archive.org PD images → static/cards/*.jpg")
    parser.add_argument("--out", default="static/cards")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--quality", type=int, default=85)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    ok, skip, fail = 0, 0, 0
    for cid in range(78):
        fname = id_to_filename(cid)
        url = FILE_BASE.format(fname)
        dest = out_dir / f"{cid:02d}.jpg"
        try:
            if dest.exists() and not args.force:
                skip += 1
                continue
            download_and_save_png_as_jpg(url, dest, args.quality)
            ok += 1
        except Exception:
            fail += 1
    print(f"archive_downloaded={ok} skipped={skip} failed={fail} -> {out_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())



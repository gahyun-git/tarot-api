#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List

import httpx


def download(url: str, dest: Path, overwrite: bool) -> bool:
    if dest.exists() and not overwrite:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache tarot card images locally from current dataset image_url")
    parser.add_argument("--data", default="data/tarot-images.json", help="path to deck json")
    parser.add_argument("--out", default="static/cards", help="output directory for images")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cards: List[dict[str, Any]] = json.loads(data_path.read_text(encoding="utf-8"))
    ok, fail, skip = 0, 0, 0
    for c in cards:
        cid = c.get("id")
        url = c.get("image_url")
        if cid is None or not url:
            skip += 1
            continue
        dest = out_dir / f"{int(cid):02d}.jpg"
        try:
            changed = download(url, dest, args.force)
            if changed:
                ok += 1
            else:
                skip += 1
        except Exception:
            fail += 1
    print(f"downloaded={ok} skipped={skip} failed={fail} -> {out_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())



#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _is_public_domain(extmetadata: dict) -> bool:
    # Commons extmetadata fields vary; check several hints
    for key in ("LicenseShortName", "License", "UsageTerms"):
        meta = extmetadata.get(key)
        if isinstance(meta, dict):
            value = str(meta.get("value", ""))
        else:
            value = str(meta or "")
        if value:
            v = value.lower()
            if "public domain" in v or v.startswith("pd-"):
                return True
    # LicenseUrl sometimes includes '/publicdomain/'
    meta = extmetadata.get("LicenseUrl")
    if isinstance(meta, dict):
        url = str(meta.get("value", ""))
    else:
        url = str(meta or "")
    if "/publicdomain/" in url:
        return True
    return False


def commons_search_image_url(card_name: str) -> Optional[str]:
    """Search Wikimedia Commons for an RWS image by card english name.

    Strategy:
    - generator=search in File namespace (6)
    - query terms: "RWS Tarot {name}" first, fallback "Rider–Waite {name}".
    - return first result's original image URL via imageinfo
    """
    queries = [f"RWS Tarot {card_name}", f"Rider-Waite {card_name}"]
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for q in queries:
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": q,
                "gsrnamespace": 6,  # File namespace
                "gsrlimit": 5,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
            }
            r = client.get(COMMONS_API, params=params)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for _, page in pages.items():
                imageinfo = page.get("imageinfo")
                if not imageinfo:
                    continue
                info = imageinfo[0]
                url = info.get("url")
                extmetadata = info.get("extmetadata") or {}
                if url and _is_public_domain(extmetadata):
                    return url
    return None


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Map to Wikimedia Commons images by card name and cache locally")
    parser.add_argument("--data", default="data/tarot-images.json")
    parser.add_argument("--out", default="static/cards")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cards: List[Dict[str, Any]] = json.loads(Path(args.data).read_text(encoding="utf-8"))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    found, skipped, failed = 0, 0, 0
    for c in cards:
        cid = int(c.get("id"))
        name = c.get("name")
        dest = out_dir / f"{cid:02d}.jpg"
        if dest.exists() and not args.force:
            skipped += 1
            continue
        try:
            url = commons_search_image_url(name)
            if not url:
                failed += 1
                continue
            download(url, dest)
            found += 1
        except Exception:
            failed += 1
    print(f"commons_downloaded={found} skipped={skipped} failed={failed} -> {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())



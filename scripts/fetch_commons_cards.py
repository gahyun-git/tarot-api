#!/usr/bin/env python3
"""
Wikimedia Commons에서 RWS 카드 원본을 다운로드하여 static/cards/*.jpg 로 저장.
파일 매핑은 0~21 메이저 아르카나에 대해 표준 파일명 기반으로 처리하고,
마이너는 기존 원격 소스를 유지하거나 수동 매핑이 필요합니다.
"""
from __future__ import annotations

from pathlib import Path

import httpx

MAJOR_FILES = [
    (0, "RWS_Tarot_00_Fool.jpg"),
    (1, "RWS_Tarot_01_Magician.jpg"),
    (2, "RWS_Tarot_02_High_Priestess.jpg"),
    (3, "RWS_Tarot_03_Empress.jpg"),
    (4, "RWS_Tarot_04_Emperor.jpg"),
    (5, "RWS_Tarot_05_Hierophant.jpg"),
    (6, "RWS_Tarot_06_Lovers.jpg"),
    (7, "RWS_Tarot_07_Chariot.jpg"),
    (8, "RWS_Tarot_08_Strength.jpg"),
    (9, "RWS_Tarot_09_Hermit.jpg"),
    (10, "RWS_Tarot_10_Wheel_of_Fortune.jpg"),
    (11, "RWS_Tarot_11_Justice.jpg"),
    (12, "RWS_Tarot_12_Hanged_Man.jpg"),
    (13, "RWS_Tarot_13_Death.jpg"),
    (14, "RWS_Tarot_14_Temperance.jpg"),
    (15, "RWS_Tarot_15_Devil.jpg"),
    (16, "RWS_Tarot_16_Tower.jpg"),
    (17, "RWS_Tarot_17_Star.jpg"),
    (18, "RWS_Tarot_18_Moon.jpg"),
    (19, "RWS_Tarot_19_Sun.jpg"),
    (20, "RWS_Tarot_20_Judgement.jpg"),
    (21, "RWS_Tarot_21_World.jpg"),
]

BASE = "https://upload.wikimedia.org/wikipedia/commons/"
# 실제 파일 경로는 해시/폴더 구조가 있으나, 'Special:FilePath'를 사용하면 원본에 리다이렉트됨
SPECIAL = "https://commons.wikimedia.org/wiki/Special:FilePath/{}"


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "static" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    for cid, fname in MAJOR_FILES:
        url = SPECIAL.format(fname)
        dest = out_dir / f"{cid:02d}.jpg"
        try:
            fetch(url, dest)
            print(f"downloaded {cid} -> {dest}")
        except Exception as e:
            print(f"failed {cid}: {e}")
    print("Done. Minor Arcana mapping not automated in this script.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

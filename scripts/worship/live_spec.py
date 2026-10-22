"""
방송 예약 정보 — script.json 시간표로 제목·설명(순서별 챕터)·시작 시각을 만든다(worship_live.py schedule 입력).

    python scripts/worship/live_spec.py output/worship/2026-10-24_ko [--preroll 300] > spec.json

시각(한국 시간 고정, 10-23 사용자: 한국·미국에 맞게):
  한국어 06:00 — 새벽기도·출근 전 / 영어 11:00 — 미국 동부 21시·서부 18시(서머타임 중엔 +1시간)
방송은 대기 화면(preroll)부터 켜지므로 예약 시각 = 예배 시각 - preroll.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))
SERVICE_AT = {"ko": "06:00", "en": "11:00"}
QT_LINK = "https://malsseum.yojosuknam.com/?src=youtube"


def stamp(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--preroll", type=int, default=300)
    a = ap.parse_args()
    s = json.loads((Path(a.folder) / "script.json").read_text(encoding="utf-8"))
    lang = s["lang"]
    hh, mm = map(int, SERVICE_AT[lang].split(":"))
    at = dt.datetime.fromisoformat(s["date"]).replace(hour=hh, minute=mm, tzinfo=KST)
    start = at - dt.timedelta(seconds=a.preroll)
    chap = []
    if a.preroll:
        chap.append(f"00:00 {'예배 준비' if lang == 'ko' else 'Gathering'}")
    for t in s["timeline"]:
        name = t["title"] if t["id"] != "sermon" else (("말씀 — " if lang == "ko" else "Sermon — ") + t["title"])
        if "song" in t:
            name += f" · {t['song']['title']}"
        chap.append(f"{stamp(t['start'] + a.preroll)} {name}")
    if lang == "ko":
        title = f"[말씀 묵상 예배] {s['title']} · {s['passage']} | {s['date'][5:].replace('-', '/')} 아침 6시"
        desc = [f"오늘의 말씀: {s['passage']}", "매일 아침 6시, 20분 실시간 예배입니다. 언제든 다시 보며 함께 예배하세요.", "",
                "📖 순서"] + chap + ["", "설교와 기도는 AI의 도움으로 준비되었고, 낭독은 운영자의 목소리를 AI로 합성했습니다.",
                                     "성경: 개역한글 · 찬양: Still Waters (yojosuknam)", "",
                                     f"📱 7섹션 큐티를 더 깊이 → 말씀Log {QT_LINK}", "", "#말씀묵상 #실시간예배 #큐티 #말씀Log"]
    else:
        title = f"[Worship in the Word] {s['title']} · {s['passage']} | Daily Live Worship"
        desc = [f"Today's passage: {s['passage']}", "A 20-minute live worship service every day "
                "(9 PM Eastern / 6 PM Pacific). Join anytime.", "", "📖 Order of Worship"] + chap + [
                "", "The sermon and prayers were prepared with the help of AI; the reading voice is an AI synthesis "
                "of the host's own voice.", "Scripture: King James Version · Music: Still Waters (yojosuknam)", "",
                f"📱 Go deeper with Malsseum Log {QT_LINK}", "", "#DailyDevotion #LiveWorship #BibleStudy"]
    json.dump({"lang": lang, "start": start.isoformat(), "title": title, "description": "\n".join(desc),
               "privacy": "public"}, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

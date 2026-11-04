#!/usr/bin/env python3
"""예배 매일 제작 운영 도우미(미니PC) — 일정 로그(schedule.jsonl)와 텔레그램 알림.

  python worship_ops.py log <stage> <status> <detail> <date> [lang=all]
      stage: voice|assemble|verify|check|deadline   status: start|ok|fail|wait
      → logs/schedule.jsonl 한 줄(JSON). ts 는 KST, date 는 그 영상을 방송할 날짜. detail 에는 비밀값을 넣지 않는다.
  python worship_ops.py notify <본문>
      → 텔레그램. 토큰·chat_id 는 ~/autovid/.env.local 에서만 읽고 POST 본문으로 보낸다(argv·로그 노출 없음).
         WORSHIP_NOTIFY=0 이면 보내지 않고 화면에만 찍는다(시험용).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

LOG_DIR = Path(os.environ.get("WORSHIP_LOG_DIR", "/mnt/external/nexis-worship/logs"))
ENV_FILE = Path(os.environ.get("WORSHIP_ENV_FILE", str(Path.home() / "autovid" / ".env.local")))
KST = dt.timezone(dt.timedelta(hours=9))
SECRET = re.compile(r"(\d{8,}:[A-Za-z0-9_-]{30,}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9_-]{20,}|rtmps?://\S+)")


def clean(s: str, n: int = 200) -> str:
    return SECRET.sub("***", " ".join(str(s).split()))[:n]


def log_event(stage: str, status: str, detail: str, date: str, lang: str = "all") -> dict:
    rec = {"ts": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"), "date": date, "lang": lang,
           "stage": stage, "status": status, "detail": clean(detail)}
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / "schedule.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def notify(text: str) -> bool:
    text = clean(text, 1500)
    if os.environ.get("WORSHIP_NOTIFY", "1") == "0":
        print("[알림-시험] " + text)
        return True
    env = {}
    try:
        for ln in ENV_FILE.read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    tok, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("[알림] 텔레그램 설정 없음 — 생략")
        return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20).read()
        return True
    except Exception as e:                       # 오류 문구에 주소(토큰)가 섞일 수 있어 종류만 남긴다
        print("[알림] 보내기 실패", type(e).__name__)
        return False


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["log"] and len(a) >= 5:
        print(json.dumps(log_event(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else "all"), ensure_ascii=False))
    elif a[:1] == ["notify"] and len(a) >= 2:
        sys.exit(0 if notify(" ".join(a[1:])) else 1)
    else:
        print(__doc__)
        sys.exit(2)

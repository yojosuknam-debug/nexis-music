"""
yojosuknam Radio 시간대 편성 — schedule.json 을 읽어 '지금 편성 / 다음 편성'을 계산한다.
streamer.py(앨범 고르기)·youtube_live.py(화면)·youtube-chat.sh(채팅)이 같이 쓴다.
한국은 서머타임이 없어 UTC+9 고정으로 계산한다(컨테이너에 tzdata 가 없어도 된다).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

PATH = Path(__file__).with_name("schedule.json")
KST = dt.timezone(dt.timedelta(hours=9))
_cache: tuple[float, dict] = (0.0, {})


def load() -> dict:
    """파일이 바뀌면 다시 읽는다(재시작 없이 편성 변경)."""
    global _cache
    try:
        mtime = PATH.stat().st_mtime
        if mtime != _cache[0]:
            _cache = (mtime, json.loads(PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return _cache[1]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def station_of(album: dict) -> str:
    """앨범의 편성 채널 — radio.json 의 station, 비어 있으면 schedule.json assign(폴더 이름)."""
    return album.get("station") or load().get("assign", {}).get(album.get("folder", ""), "")


def block_at(ts: float) -> dict:
    """ts(유닉스 초) 가 속한 편성 칸. {'station', 'start', 'end'(유닉스 초), 'regular'(정규 방송 여부)}"""
    s = load()
    blocks = sorted(s.get("blocks", []), key=lambda b: _minutes(b["start"]))
    if not blocks:
        return {"station": "", "start": ts, "end": ts + 3600, "regular": True}
    now = dt.datetime.fromtimestamp(ts, KST)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    cur = now.hour * 60 + now.minute
    i = max((k for k, b in enumerate(blocks) if _minutes(b["start"]) <= cur), default=-1)
    start = day + dt.timedelta(minutes=_minutes(blocks[i]["start"]))
    if i == -1:                                   # 첫 칸보다 이르면 전날 마지막 칸
        start -= dt.timedelta(days=1)
    j = (i + 1) % len(blocks)
    end = day + dt.timedelta(minutes=_minutes(blocks[j]["start"]))
    if end <= start:
        end += dt.timedelta(days=1)
    r0, r1 = (_minutes(x) for x in s.get("regular", ["07:00", "22:00"]))
    sm = start.hour * 60 + start.minute
    return {"station": blocks[i]["station"], "start": start.timestamp(), "end": end.timestamp(),
            "regular": r0 <= sm < r1}


def program(ts: float, station: str = "") -> tuple[dict, dict]:
    """지금 나오는 곡(ts, 그 곡의 채널) 기준 (지금 칸, 다음 칸).
    앨범이 칸 경계를 넘겨 이어지는 중이면 앞 칸을 '지금'으로 본다."""
    cur = block_at(ts)
    if station and cur["station"] != station:
        prev, nxt = block_at(cur["start"] - 1), block_at(cur["end"] + 1)
        if prev["station"] == station and ts - cur["start"] < 40 * 60:
            cur = prev                            # 앞 칸 앨범이 경계를 넘겨 이어지는 중
        elif nxt["station"] == station and cur["end"] - ts < 15 * 60:
            cur = nxt                             # 다음 칸 앨범을 조금 일찍 시작함
    return cur, block_at(cur["end"] + 1)


def info(station: str) -> dict:
    return load().get("stations", {}).get(station, {})


def hhmm(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, KST).strftime("%H:%M")


def timetable_text() -> str:
    """유튜브 설명란용 편성표 글. 정규 방송은 채널별 시작 시각 묶음, 심야는 시간순."""
    s = load()
    st = s.get("stations", {})
    blocks = sorted(s.get("blocks", []), key=lambda b: _minutes(b["start"]))
    r0, r1 = (_minutes(x) for x in s.get("regular", ["07:00", "22:00"]))
    lab = lambda name: f"{st.get(name, {}).get('icon', '')} {name}".strip()
    day: dict[str, list[str]] = {}
    for b in blocks:
        if r0 <= _minutes(b["start"]) < r1:
            day.setdefault(b["station"], []).append(b["start"])
    night = [b for b in blocks if _minutes(b["start"]) >= r1] + [b for b in blocks if _minutes(b["start"]) < r0]
    out = ["📅 편성표 (한국 시간 · 앨범 단위라 10~20분 앞뒤로 움직여요)", "",
           f"[정규 방송 {s.get('regular', ['07:00'])[0]}–{s.get('regular', ['', '22:00'])[1]}]"]
    for name, times in day.items():
        out.append(f"{' · '.join(times)}  {lab(name)} — {st.get(name, {}).get('genre', '')}")
    out += ["", f"[심야 방송 {s.get('regular', ['', '22:00'])[1]}–{s.get('regular', ['07:00'])[0]} · 로파이 위주]"]
    out += [f"{b['start']}  {lab(b['station'])}" for b in night]
    out += ["", "📺 채널"] + [f"{lab(name)}  {v.get('url', '')}" for name, v in st.items()]
    return "\n".join(out)

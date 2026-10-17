"""우리 곡 ↔ 유튜브 영상 짝짓기. build_pages.py 가 쓴다. 재료 = fetch_yt_music.py 가 받은 assets/*.json

곡마다 링크를 이 순서로 정한다.
  1) 그 곡 하나짜리 영상(채널 6곳, 2분 이상)         — 제목 + 길이(15초 이내)
  2) 앨범 전체 영상에서 그 곡이 시작되는 지점(&t=초) — 앨범마다 수록곡이 가장 많이 겹치는 영상을 먼저 고른다
  3) 유튜브 뮤직 Topic 곡(유통 음원)                 — 제목 + 길이
앨범 영상 링크도 2)의 전체 영상으로 정한다(커버 사진만 같은 61초 쇼츠로 잘못 이어지던 것 바로잡음).

제목 표기가 제각각이다('늦은 축가 (A Late Toast)' ↔ '늦은 축가' / 'A Late Toast').
전체·괄호 앞·괄호 안을 각각 정규화해 하나라도 같으면 같은 곡 후보로 본다.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
# 유튜브 채널 6곳 — 방송 화면에서 채널별 색·소개가 바뀐다(scripts/radio/youtube_live.py THEMES 와 이름이 같아야 함)
STATIONS = ("Miso Beats", "Midnight Radio", "Hanguk Sounds", "굳이 송", "Still Waters", "쉬어가는 감성 음악")


def station_from_hint(hint: str) -> str:
    """album.md 의 채널 표기(제각각)를 6개 채널 이름으로. 모르면 ''."""
    h = (hint or "").lower()
    rules = (("still", "Still Waters"), ("굳이", "굳이 송"), ("gudi", "굳이 송"), ("guji", "굳이 송"),
             ("hanji", "Hanguk Sounds"), ("한지", "Hanguk Sounds"), ("한국전통", "Hanguk Sounds"),
             ("hanguk", "Hanguk Sounds"), ("korean traditional", "Hanguk Sounds"),
             ("감성", "쉬어가는 감성 음악"), ("gamseong", "쉬어가는 감성 음악"), ("retro", "쉬어가는 감성 음악"),
             ("복고", "쉬어가는 감성 음악"), ("miso channel", "쉬어가는 감성 음악"),
             ("miso", "Miso Beats"), ("lofi", "Midnight Radio"), ("lo-fi", "Midnight Radio"))
    for key, name in rules:
        if key in h:
            return name
    return ""
SINGLE_MIN_MS = 120_000           # 이보다 짧은 영상은 쇼츠·예고편


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^\w]|_", "", s)


def variants(title: str) -> set[str]:
    title = re.sub(r"\s*[—–|]\s+.*$", "", title)          # 영상 제목의 ' — 설명 | 태그' 꼬리
    out = {title}
    m = re.match(r"^(.*?)\s*[(\[（](.*)[)\]）]\s*$", title)
    if m:
        out |= {m.group(1), m.group(2)}
        out |= {x.strip() for x in re.split(r"\s+[—–-]\s+|,", m.group(2)) if x.strip()}
    return {n for n in (norm(x) for x in out) if len(n) >= 2}


def _load(name: str) -> list[dict]:
    p = ASSETS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


class Links:
    def __init__(self) -> None:
        vids = _load("yt_videos.json")
        self.channel_of = {v["id"]: v.get("ch", "") for v in vids}
        self.albums = [v for v in vids if v.get("chapters")]
        self.singles: dict[str, list[dict]] = {}
        for v in vids:
            if not v.get("chapters") and v["ms"] >= SINGLE_MIN_MS:
                for k in variants(v["title"]):
                    self.singles.setdefault(k, []).append(v)
        self.topic: dict[str, list[dict]] = {}
        for t in _load("yt_music.json"):
            for k in variants(t["title"]):
                self.topic.setdefault(k, []).append(t)
        for v in self.albums:
            v["_chv"] = [(sec, variants(title)) for sec, title in v["chapters"]]

    @staticmethod
    def _closest(cands: list[dict], ms: int, limit: int) -> dict | None:
        best = min(cands, key=lambda c: abs(c.get("ms", 0) - ms), default=None)
        return best if best and abs(best.get("ms", 0) - ms) <= limit else None

    def _album_video(self, tracks: list[dict]) -> tuple[dict | None, dict[int, int]]:
        """수록곡이 가장 많이 겹치는 앨범 전체 영상과, 곡 번호 → 시작 초."""
        best, best_hits = None, {}
        for v in self.albums:
            hits = {}
            for t in tracks:
                tv = variants(t["title"])
                for sec, cv in v["_chv"]:
                    if tv & cv:
                        hits[t["n"]] = sec
                        break
            if len(hits) > len(best_hits):
                best, best_hits = v, hits
        need = 1 if len(tracks) == 1 else max(2, (len(tracks) + 1) // 2)
        if len(best_hits) < need:
            return None, {}
        # 시간표 줄 수가 수록곡 수와 같으면 못 맞춘 곡은 순서대로 채운다
        if len(best["chapters"]) == len(tracks):
            for i, t in enumerate(tracks):
                best_hits.setdefault(t["n"], best["chapters"][i][0])
        return best, best_hits

    def album(self, tracks: list[dict]) -> tuple[str, dict[int, str]]:
        """(앨범 영상 링크, {곡 번호: 곡 링크}). tracks = [{n, title, ms}]"""
        video, starts = self._album_video(tracks)
        links: dict[int, str] = {}
        for t in tracks:
            single = self._closest([c for k in variants(t["title"]) for c in self.singles.get(k, [])], t["ms"], 15000)
            if single:
                links[t["n"]] = f"https://www.youtube.com/watch?v={single['id']}"
            elif video and t["n"] in starts:
                links[t["n"]] = f"https://www.youtube.com/watch?v={video['id']}&t={starts[t['n']]}s"
            else:
                tp = self._closest([c for k in variants(t["title"]) for c in self.topic.get(k, [])], t["ms"], 15000)
                if tp:
                    links[t["n"]] = f"https://music.youtube.com/watch?v={tp['id']}"
        return (f"https://www.youtube.com/watch?v={video['id']}" if video else ""), links

    def station(self, video_url: str, hint: str = "") -> str:
        """앨범이 원래 올라간 유튜브 채널 — 영상이 있으면 그 채널, 없으면 album.md 표기로."""
        m = re.search(r"v=([\w-]{11})", video_url or "")
        ch = self.channel_of.get(m.group(1), "") if m else ""
        return ch if ch in STATIONS else station_from_hint(hint)

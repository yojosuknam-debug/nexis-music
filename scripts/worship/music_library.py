"""
예배 음악 대장(music.json) — 곡마다 종류·언어·권리 근거를 적어 두고, 예배 자리(slot)에 맞는 곡만 고른다.
설계: docs/worship-order.md · 저작권 근거: docs/research/2026-10-24_예배-찬송가-저작권.md

    python scripts/worship/music_library.py sync            # Still Waters 채널 곡을 대장에 반영(사람이 고친 종류·권리는 유지)
    python scripts/worship/music_library.py add <폴더>       # 직접 연주·자작 곡 폴더(meta.json)를 대장에 추가
    python scripts/worship/music_library.py list [slot] [lang]

종류(type)
  hymn_pd       함께 부르는 찬송 — 저작권 만료 곡, 운영자 직접 피아노 반주(+ 가사 자막)
  hymn_own      자작 찬송가 — 찬송가 작법으로 만든 자작곡(Suno), 채널 업로드
  ccm           자작 CCM — 채널의 보컬 곡(기본값)
  instrumental  연주곡 — 기도회 배경(채널 연주곡·자작 찬송 연주판·직접 연주 모두)
권리(license.status): verified 만 예배에 나온다. pending/blocked 는 대장에만 둔다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import slides as sl

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "music.json"
RADIO_JSON = "https://music.yojosuknam.com/album/radio.json"
OWN_BASIS = "자작곡(Still Waters 채널, Suno 유료 플랜 공식 다운로드 — 운영자 확인)"
HYMN_ALBUM = re.compile(r"찬송|hymn", re.I)   # 앨범 제목에 있으면 그 앨범 보컬 곡 = 자작 찬송가(hymn.md 5장)

# 예배 자리별 쓸 수 있는 종류(앞쪽 우선). 비면 FALLBACK 으로.
SLOT_TYPES = {"open": ["hymn_pd", "hymn_own"], "response": ["hymn_own", "ccm"], "prayer": ["instrumental"]}
FALLBACK = {"open": ["ccm"], "response": ["hymn_pd"], "prayer": []}
SLOT_SEC = {"open": (90, 330), "response": (90, 330), "prayer": (90, 900)}   # 곡 길이(초) 범위


def load() -> list[dict]:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []


def save(items: list[dict]) -> None:
    items.sort(key=lambda x: (x["source"], x["id"]))
    LEDGER.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def guess_lang(lines: list[str]) -> str:
    text = " ".join(lines)
    return "ko" if re.search(r"[가-힣]", text) else "en"


def base_title(title: str) -> str:
    return re.sub(r"\s*\((연주|instrumental|prayer instrumental)\)\s*$", "", title, flags=re.I).strip().lower()


def pair(items: dict) -> None:
    """같은 앨범의 '<제목> (연주)/(Instrumental)' 연주곡을 보컬판과 짝지운다 — 기도회 배경으로 먼저 쓰인다.
    (youtube-playlist docs/album-system/40_genres/hymn.md 5장 제목 규칙)"""
    by_album: dict[str, dict] = {}
    for x in items.values():
        by_album.setdefault(x.get("slug", x["id"]), {})
    for x in items.values():
        if x["type"] != "instrumental" and x.get("source") == "stillwaters":
            by_album[x["slug"]][base_title(x["title"])] = x
    for x in items.values():
        if x["type"] == "instrumental" and x.get("source") == "stillwaters":
            v = by_album.get(x["slug"], {}).get(base_title(x["title"]))
            if v and base_title(x["title"]) != x["title"].strip().lower():
                x["instrumental_of"], v["instrumental"] = v["id"], x["id"]


def sync() -> None:
    """Still Waters 앨범 페이지의 곡을 대장에 넣는다. 종류: instrumental 표시·가사 없음 → 연주곡, 나머지 → ccm.
    이미 있는 곡은 사람이 바꾼 type·lang·credits·license 를 그대로 두고 주소·길이만 갱신한다."""
    have = {x["id"]: x for x in load()}
    data = json.loads(sl.fetch(RADIO_JSON))
    added = 0
    for a in data["albums"]:
        if a.get("station") != "Still Waters":
            continue
        html = sl.fetch(a["page"]).decode("utf-8")
        m = re.search(r"window\.ALBUM\s*=\s*(\{.*?\});\s*</script>", html, re.S)
        page = {str(t.get("n")): t for t in (json.loads(m.group(1)).get("tracks", []) if m else [])}
        for t in a["tracks"]:
            p = page.get(str(t["n"]), {})
            lines = [ln for sec in (p.get("lyrics") or []) if isinstance(sec, dict) for ln in sec.get("lines") or []]
            inst = bool(p.get("instrumental")) or not lines
            key = f"sw:{a['slug']}:{t['n']}"
            base = {"id": key, "source": "stillwaters", "title": t["title"], "album": a["title"], "slug": a["slug"],
                    "n": t["n"], "page": a["page"], "url": t["url"], "youtube": t.get("youtube", ""),
                    "cover": a.get("cover", ""), "ms": int(t.get("ms") or 0)}
            if key in have:
                have[key].update(base)
                continue
            hymn_album = bool(HYMN_ALBUM.search(a["title"]))
            have[key] = {**base, "type": "instrumental" if inst else ("hymn_own" if hymn_album else "ccm"),
                         "lang": "none" if inst else guess_lang(lines),
                         "credits": {"lyricist": "운영자", "composer": "운영자(Suno)", "arranger": "", "translator": ""},
                         "license": {"status": "verified", "basis": OWN_BASIS, "evidence": t.get("youtube", "")}}
            added += 1
    pair(have)
    save(list(have.values()))
    kinds = {}
    for x in have.values():
        kinds[x["type"]] = kinds.get(x["type"], 0) + 1
    print(f"대장 {len(have)}곡 (새로 {added}) · 종류별 {kinds}")


def add(folder: str) -> None:
    """직접 연주·자작 곡 폴더 → 대장. meta.json 예시는 docs/worship-order.md '곡 보내는 법'."""
    d = Path(folder)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    for k in ("id", "title", "type", "lang", "file", "credits", "license"):
        if k not in meta:
            sys.exit(f"meta.json 에 {k} 가 없다")
    items = [x for x in load() if x["id"] != meta["id"]]
    items.append({**meta, "source": "local", "folder": d.name})
    save(items)
    print(f"추가 {meta['id']} · {meta['type']} · {meta['license']['status']}")


def lyrics_cues(folder: Path, lyrics_file: str, total_sec: float) -> list[dict]:
    """가사.txt → 두 줄씩 [{start,end,lines}]. 절은 빈 줄로 나누고, 절 첫 줄에 '@0:12' 가 있으면 그 시각부터.
    시각이 없는 절은 남은 시간(전주 8초 뒤)을 고르게 나눈다."""
    raw = (folder / lyrics_file).read_text(encoding="utf-8").strip()
    blocks, starts = [], []
    for b in re.split(r"\n\s*\n", raw):
        ls = [x.strip() for x in b.splitlines() if x.strip()]
        m = re.match(r"^@(\d+):(\d\d)$", ls[0]) if ls else None
        starts.append(int(m[1]) * 60 + int(m[2]) if m else None)
        blocks.append(ls[1:] if m else ls)
    n = len(blocks)
    even = [8 + i * (total_sec - 8) / n for i in range(n)]
    st = [s if s is not None else even[i] for i, s in enumerate(starts)]
    out = []
    for i, ls in enumerate(blocks):
        a, b = st[i], st[i + 1] if i + 1 < n else total_sec - 2
        pairs = [ls[j:j + 2] for j in range(0, len(ls), 2)] or [[""]]
        step = (b - a) / len(pairs)
        out += [{"start": a + k * step, "end": a + (k + 1) * step, "lines": p} for k, p in enumerate(pairs)]
    return out


def candidates(slot: str, lang: str, types: list[str]) -> list[dict]:
    lo, hi = SLOT_SEC[slot]
    out = []
    for x in load():
        if x.get("license", {}).get("status") != "verified" or x["type"] not in types:
            continue
        if x["type"] != "instrumental" and x.get("lang") != lang:
            continue
        sec = (x.get("ms") or 0) / 1000
        if x["source"] == "stillwaters" and not lo <= sec <= hi:
            continue
        out.append(x)
    return sorted(out, key=lambda x: x["id"])


def pick(slot: str, lang: str, ordinal: int, avoid: set[str] = frozenset()) -> dict:
    """그날 그 자리의 곡 1개 — 종류 우선순위대로, 날짜로 돌려 가며. 없으면 FALLBACK."""
    for types in [[t] for t in SLOT_TYPES[slot]] + ([FALLBACK[slot]] if FALLBACK[slot] else []):
        cand = [x for x in candidates(slot, lang, types) if x["id"] not in avoid]
        if cand:
            return dict(cand[(ordinal * 7 + len(slot)) % len(cand)])
    raise RuntimeError(f"'{slot}' 자리에 쓸 {lang} 곡이 대장에 없습니다(verified)")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "sync":
        sync()
    elif cmd == "add":
        add(sys.argv[2])
    else:
        slot = sys.argv[2] if len(sys.argv) > 2 else None
        lang = sys.argv[3] if len(sys.argv) > 3 else "ko"
        for x in (candidates(slot, lang, SLOT_TYPES[slot] + FALLBACK[slot]) if slot else load()):
            print(f"{x['type']:12s} {x.get('lang', ''):4s} {x['license']['status']:8s} {x['id']:55s} {x['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
1단계 — 앨범 카탈로그 수집기

영상 제작 파이프라인의 input/ 폴더에서 앨범을 읽어 사이트가 쓸 catalog.json 을 만든다.
LLM 호출 없음. 순수 파싱 + ffprobe.

  * 제목·장르·가사   ← <앨범>/*album*.md
  * 트랙 파일·길이    ← <앨범>/tracks/NN_*.mp3  (번호 접두사가 트랙 번호)
  * 커버              ← 라이브 data.js 의 유튜브 썸네일 (제목 매칭)

🔴 album.md 에는 가사 바로 위에 Suno 프롬프트가 들어 있다. 앨범 제작 노하우 그 자체라
   사이트로 나가면 안 된다. 여기서는 ### Lyrics / ### Suno 가사 코드펜스 **안쪽만** 읽고,
   프롬프트 블록은 애초에 건드리지 않는다.

사용법:
    python scripts/jukebox/scan_albums.py             # 카탈로그 생성
    python scripts/jukebox/scan_albums.py --report    # 생성 없이 커버리지만 출력
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env

REPO = Path(__file__).resolve().parents[2]
INPUT_DIR = _env.input_dir()      # 미니PC면 원본, 데스크탑이면 사본
LIVE_DATA = REPO / "public" / "data.js"
OUT = REPO / "scripts" / "jukebox" / "catalog.json"

TRACK_RE = re.compile(r"^##\s*Track\s*(\d+)\s*[:.]?\s*(.*)$", re.M | re.I)
# 가사 소제목은 영/한 변형이 둘 다 존재한다: "### Lyrics", "### Suno 가사", "### 가사"
LYRICS_RE = re.compile(r"^###[^\n]*(?:Lyrics|가사)[^\n]*\n+```[a-z]*\n(.*?)```", re.S | re.M | re.I)
INSTRUMENTAL_RE = re.compile(r"\[\s*(?:Instrumental|No vocals)\s*\]", re.I)
SECTION_RE = re.compile(r"^\[(.+?)\]$")
TIMECODE_RE = re.compile(r"^\(\s*\d+:\d\d\s*[-~]\s*\d+:\d\d\s*\)$")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


# ── 슬러그 ────────────────────────────────────────────────────────────────
def slugify(value: str) -> str:
    """한글을 보존한다. [^a-z0-9] 로 뭉개면 한글 전용 제목이 전부 빈 문자열이 되어
    서로 다른 앨범이 같은 slug 로 충돌한다(2026-08-05 실제 사고)."""
    s = unicodedata.normalize("NFC", EMOJI_RE.sub(" ", value)).lower()
    s = re.sub(r"[^\w\uac00-\ud7a3]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "album"


# ── 라이브 사이트에서 커버 찾기 ────────────────────────────────────────────
def load_live() -> list[dict]:
    raw = LIVE_DATA.read_text(encoding="utf-8")
    m = re.search(r"'([A-Za-z0-9+/=]+)'", raw)
    if not m:
        return []
    return json.loads(base64.b64decode(m.group(1)).decode("utf-8"))


def norm(s: str) -> str:
    s = EMOJI_RE.sub(" ", s).lower()
    s = re.sub(r"#\s*shorts?", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"vol\s*\.?\s*\d+", " ", s)
    s = re.sub(r"^\s*album\s*[:：]", " ", s)
    s = re.sub(r"[^\w\uac00-\ud7a3]+", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def album_candidates(live_title: str) -> list[str]:
    """라이브 제목은 대부분 '곡명 — 앨범명 #Shorts' 꼴이다.
    구분자 뒤(앨범명)와 전체 둘 다 후보로 둔다. 전체만 쓰면 6/68 밖에 안 붙는다."""
    t = EMOJI_RE.sub(" ", live_title)
    parts = re.split(r"\s[—–|]\s|\s-\s", t)
    out = [parts[-1]] if len(parts) > 1 else []
    out.append(t)
    return [c for c in (norm(x) for x in out) if c]


def track_candidates(live_title: str) -> list[str]:
    """'🎵 툭 쳐 — 굳이 그렇게까지' 에서 구분자 **앞**(곡명)을 뽑는다.
    앨범명으로 못 찾은 앨범을 수록곡 제목으로 다시 찾기 위한 것."""
    t = EMOJI_RE.sub(" ", live_title)
    head = re.split(r"\s[—–|]\s|\s-\s", t)[0]
    c = norm(head)
    return [c] if c else []


def find_cover_by_tracks(tracks: list[dict], index: list[tuple[list[str], dict]]) -> tuple[str, float, int]:
    """수록곡 제목으로 라이브 영상을 찾아 그 썸네일을 앨범 커버로 쓴다.
    한 곡만 맞으면 우연일 수 있으므로 2곡 이상 맞을 때만 채택하고,
    커버는 가장 앞 트랙(대표곡)의 것을 쓴다."""
    hits: list[tuple[int, str, float]] = []
    for t in tracks:
        key = norm(t["title"])
        if len(key) < 2:
            continue
        best, score = None, 0.0
        for cands, row in index:
            for c in cands:
                s = difflib.SequenceMatcher(None, key, c).ratio()
                if key and c and (key in c or c in key) and abs(len(key) - len(c)) < 10:
                    s = max(s, 0.92)
                if s > score:
                    score, best = s, row
        if best and score >= 0.86 and best.get("thumbnail_url"):
            hits.append((t["n"], best["thumbnail_url"], score))
    if len(hits) < 2:
        return "", 0.0, len(hits)
    hits.sort(key=lambda x: x[0])
    return hits[0][1], round(sum(h[2] for h in hits) / len(hits), 2), len(hits)


def find_cover(key: str, index: list[tuple[list[str], dict]]) -> tuple[str, float]:
    best, score = None, 0.0
    for cands, row in index:
        for c in cands:
            s = difflib.SequenceMatcher(None, key, c).ratio()
            if key and c and (key in c or c in key):
                s = max(s, 0.90 if abs(len(key) - len(c)) < 14 else 0.80)
            if s > score:
                score, best = s, row
    if best and score >= 0.72:
        return best.get("thumbnail_url", ""), round(score, 2)
    return "", round(score, 2)


# ── 가사 ──────────────────────────────────────────────────────────────────
def parse_lyrics(block: str) -> tuple[list[dict], bool]:
    """[Verse 1] 같은 구획을 살려 구조화한다. (0:22-1:05) 구간시각 줄은 화면에 안 쓰므로 뺀다.
    반환: (구획 목록, 연주곡 여부)"""
    m = LYRICS_RE.search(block)
    if not m:
        return [], False
    raw = m.group(1).strip()
    if INSTRUMENTAL_RE.search(raw) and len(re.sub(r"\[.*?\]", "", raw).strip()) < 30:
        return [], True

    sections: list[dict] = []
    tag, buf = None, []

    def flush():
        if tag or buf:
            sections.append({"tag": tag, "lines": buf[:]})

    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        hit = SECTION_RE.match(s)
        if hit:
            flush()
            tag, buf[:] = hit.group(1), []
            continue
        if TIMECODE_RE.match(s):
            continue
        buf.append(s)
    flush()
    return sections, False


def clean_track_title(s: str) -> str:
    """'쨍과리 디스코 (Kkwaenggwari Disco) — 🎤 Vocal' 의 제작용 꼬리표를 뗀다."""
    return re.split(r"\s+[—–]\s+", s)[0].strip() or s


def duration_ms(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()
    try:
        return int(float(out) * 1000)
    except ValueError:
        return 0


# ── 앨범 하나 ─────────────────────────────────────────────────────────────
def scan_album(folder: Path, index, track_index) -> dict | None:
    mds = sorted(folder.glob("*album*.md"))
    if not mds:
        return None
    md = max(mds, key=lambda p: p.stat().st_mtime)          # 개정본(V4 등) 우선
    text = md.read_text(encoding="utf-8", errors="replace")

    title = re.sub(r"^\s*Album\s*[:：]\s*", "", text.split("\n", 1)[0].lstrip("# ").strip())
    def meta(field):
        m = re.search(rf"^\*\*{field}\*\*\s*[:：]\s*(.+)$", text, re.M)
        return m.group(1).strip() if m else ""

    # mp3 는 파일명 앞 숫자가 트랙 번호다 (tracks/01_....mp3)
    audio: dict[int, Path] = {}
    for f in sorted(folder.rglob("*.mp3")):
        m = re.match(r"(\d+)", f.name)
        if m:
            audio.setdefault(int(m.group(1)), f)

    hits = list(TRACK_RE.finditer(text))
    tracks = []
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        block = text[h.start():end]
        n = int(h.group(1))
        f = audio.get(n)
        sections, instrumental = parse_lyrics(block)
        tracks.append({
            "n": n,
            "title": clean_track_title(h.group(2)),
            "file": f.name if f else "",
            "src": str(f) if f else "",
            "ms": duration_ms(f) if f else 0,
            "instrumental": instrumental,
            "lyrics": sections,
        })

    # 1차: 앨범명으로 찾는다. 안 되면 2차: 수록곡 제목으로 찾는다.
    cover_url, score = find_cover(norm(title), index)
    how = "album" if cover_url else ""
    if not cover_url:
        cover_url, score, n_hit = find_cover_by_tracks(tracks, track_index)
        if cover_url:
            how = f"tracks({n_hit}곡)"

    return {
        "folder": folder.name,
        "slug": slugify(title),
        "title": title,
        "genre": meta("Genre"),
        "channel": meta("Channel"),
        "tracks": tracks,
        "cover_source": cover_url,
        "cover_match": score,
        "cover_how": how,
        "total_ms": sum(t["ms"] for t in tracks),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="파일을 쓰지 않고 커버리지만 출력")
    args = ap.parse_args()

    if not INPUT_DIR.exists():
        print(f"[에러] 앨범 원본 폴더를 찾을 수 없습니다: {INPUT_DIR}")
        return 1

    live = load_live()
    index = [(album_candidates(r.get("title", "")), r) for r in live]
    track_index = [(track_candidates(r.get("title", "")), r) for r in live]
    albums, seen = [], {}
    for d in sorted(p for p in INPUT_DIR.iterdir() if p.is_dir()):
        a = scan_album(d, index, track_index)
        if not a:
            continue
        # slug 충돌은 조용히 덮어쓰면 앨범이 사라진다 — 폴더명을 붙여 분리한다
        if a["slug"] in seen:
            a["slug"] = f"{a['slug']}-{slugify(a['folder'])}"
        seen[a["slug"]] = True
        albums.append(a)

    n_tracks = sum(len(a["tracks"]) for a in albums)
    n_audio = sum(1 for a in albums for t in a["tracks"] if t["src"])
    n_lyrics = sum(1 for a in albums for t in a["tracks"] if t["lyrics"])
    n_inst = sum(1 for a in albums for t in a["tracks"] if t["instrumental"])
    n_cover = sum(1 for a in albums if a["cover_source"])

    print(f"앨범 {len(albums)}개 · 트랙 {n_tracks}곡")
    print(f"  음원 연결   {n_audio:>4}곡  ({n_audio*100//max(n_tracks,1)}%)")
    print(f"  가사 있음   {n_lyrics:>4}곡  · 연주곡 {n_inst}곡 · 미확인 {n_tracks-n_lyrics-n_inst}곡")
    print(f"  커버 확보   {n_cover:>4}앨범 ({n_cover*100//max(len(albums),1)}%)")

    missing = [a for a in albums if not a["cover_source"]]
    if missing:
        print(f"\n커버 없는 앨범 {len(missing)}개 (대체 커버 생성 대상):")
        for a in missing:
            print(f"   {a['folder']:30s} 매칭점수 {a['cover_match']:.2f}  {a['title'][:34]}")
    by_track = [a for a in albums if a.get("cover_how","").startswith("tracks")]
    if by_track:
        print(f"\n수록곡으로 커버를 찾은 앨범 {len(by_track)}개:")
        for a in by_track:
            print(f"   {a['folder']:30s} {a['cover_how']:12s} 평균 {a['cover_match']:.2f}  {a['title'][:30]}")

    if not args.report:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(albums, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {OUT.relative_to(REPO)} ({OUT.stat().st_size//1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

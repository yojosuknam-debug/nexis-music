"""
예배 영상 조립 — build_worship.py 가 만든 script.json·mp3 + slides.py 화면 → 1920×1080 mp4.

    python scripts/worship/render_video.py output/worship/2026-10-22_ko [--preroll 300]

화면이 바뀌는 때:
- 낭독(부름·기도·말씀·결단 기도·주기도문·축복): 묶음(chunk_secs) 안에서 문장 길이 비례로 문장 자막
  (chunk_secs 가 없는 옛 결과는 긴 쉼 N-1곳을 찾아 묶음 경계로 쓴다)
- 성경 봉독: 절마다 큰 명조 화면
- 찬양: 가사 구간 시간표(0:14-0:42)로 두 줄씩, 가사 없는 때는 곡 제목 화면
--preroll: 라이브용 '곧 시작합니다' 화면(초). 카운트다운은 분 단위로 바뀐다.
대부분 정지 화면이라 x264 stillimage 로 빠르게 굽는다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_worship as bw  # noqa: E402
import slides as sl  # noqa: E402

GAP = 1.5          # build_worship.mix 의 apad
FPS = 30


def silences(wav: str) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "silencedetect=n=-40dB:d=0.35", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(st, en))


def chunk_times(p: dict, n: int) -> list[float]:
    """묶음별 길이(초, 늘리기 전)."""
    secs = (p.get("qc") or {}).get("chunk_secs")
    if secs and len(secs) == n:
        return secs
    total = bw.dur(Path(p["audio"]))
    sil = silences(p["audio"])
    cuts = sorted(sorted(sil, key=lambda s: s[1] - s[0], reverse=True)[: n - 1], key=lambda s: s[0])
    bounds = [0.0] + [e for _, e in cuts] + [total]
    return [b - a for a, b in zip(bounds, bounds[1:])]


def split_long(s: str, lim: int) -> list[str]:
    """자막은 화면에 3줄까지만 그려져 넘치면 잘렸다(10-24 '안녕하…') → 쉼표에서, 그래도 길면 띄어쓰기에서 lim 안으로 나눈다."""
    if len(s) <= lim:
        return [s]
    out, cur = [], ""
    for piece in re.split(r"(?<=,)\s+", s):
        if cur and len(cur) + len(piece) > lim:
            out.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    out += [cur] if cur else []
    res = []
    for x in out:                                  # 쉼표가 없는 긴 조각 — 가운데 가까운 띄어쓰기에서 반으로
        while len(x) > lim:
            cut = x.rfind(" ", 0, min(lim, len(x) // 2 + 1))
            cut = cut if cut > 0 else lim
            res.append(x[:cut].strip())
            x = x[cut:].strip()
        res.append(x)
    return [x for x in res if x]


def sentences(chunk: str, lang: str) -> list[str]:
    out = []
    for s in re.split(r"(?<=[.!?])\s+", bw.display_ref(chunk, lang)):   # 자막은 장·절을 숫자로
        if s.strip():
            out += split_long(s.strip(), 56 if lang == "ko" else 110)   # 두 줄 안
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--preroll", type=int, default=0)
    a = ap.parse_args()
    folder = Path(a.folder)
    s = json.loads((folder / "script.json").read_text(encoding="utf-8"))
    lang, date = s["lang"], s["date"]
    parts = {p["id"]: p for p in s["parts"]}
    mp3 = folder / f"worship_{date}_{lang}.mp3"
    fr = folder / "frames"
    fr.mkdir(exist_ok=True)
    for old in fr.glob("*.png"):
        old.unlink()
    seq: list[tuple[Path, float]] = []
    cache: dict[str, Path] = {}

    def add(key: str, make, sec: float) -> None:
        if sec <= 0.05:
            return
        if key not in cache:
            path = fr / f"{len(cache):04d}.png"
            make().save(path)
            cache[key] = path
        seq.append((cache[key], sec))

    bg_topic = sl.topic_bg(s["title"] + parts["sermon"]["text"][:400])
    bgs = {"call": sl.BG_DIR / "예배.png", "prayer": sl.BG_DIR / "기도.png", "sermon": bg_topic,
           "closing": sl.BG_DIR / "기도.png", "lords_prayer": sl.BG_DIR / "기도.png", "blessing": sl.BG_DIR / "평안.png"}
    L = sl.LABELS[lang]
    order_name = dict(L["order"])

    if a.preroll:
        title = s["title"]
        for m in range(a.preroll // 60, 0, -1):
            msg = f"{m}분 뒤 예배가 시작됩니다" if lang == "ko" else f"Worship begins in {m} minute{'s' if m > 1 else ''}"
            add(f"pre{m}", lambda msg=msg: sl.caption(lang, date, "", L["service"], title, msg, sl.BG_DIR / "예배.png"), 60)

    for t in s["timeline"]:
        p = parts[t["id"]]
        sec_total = t["sec"]
        if "song" in p:
            sp = p["song"]
            try:
                lyr = sp.get("lyrics_cues") or sl.song_lyrics(sp["page"], sp["n"])   # 직접 연주 찬송은 가사.txt 시각표
            except Exception:  # noqa: BLE001
                lyr = []
            name = re.sub(r"\s*\(.*\)\s*$", "", sp["title"]) if lang == "ko" else (
                (re.search(r"\((.*)\)", sp["title"]) or re.match(r"(.*)", sp["title"])).group(1))
            title_card = lambda: sl.song(lang, date, t["id"], sp["title"], [name], sl.BG_DIR / "예배.png", sp.get("youtube", ""))
            cur = 0.0
            for k, sec in enumerate(lyr):
                st, en = min(sec["start"], sec_total), min(sec["end"], sec_total)
                add(f"{t['id']}title", title_card, st - cur)
                add(f"{t['id']}ly{k}", lambda sec=sec: sl.song(lang, date, t["id"], sp["title"], sec["lines"],
                                                               sl.BG_DIR / "예배.png", sp.get("youtube", "")), en - st)
                cur = max(cur, en)
            add(f"{t['id']}title", title_card, sec_total - cur)
            continue

        if "pm" in p:                             # 기도회 — 인도 문장(자막) → 함께 기도하는 동안 제목을 띄워 둔다
            pray = "함께 기도합니다" if lang == "ko" else "Let us pray together"
            texts = {"intro": p["pm"]["intro"], "close": p["pm"]["close"],
                     **{f"topic{i + 1}": x for i, x in enumerate(p["pm"]["topics"])}}
            pm_slow = p.get("pm_speed", bw.SPEED)
            used = 0.0
            for mk in t["pm_marks"]:
                lead = texts[mk["k"]]
                speak = mk["speak_end"] - mk["start"]
                # 마디 안은 실제 묶음 길이(chunk_secs)로 — 글자 수 비례만 쓰면 짧은 인사 뒤 긴 문장에서 어긋났다
                cks = bw.chunks(lead, lang, pm=True)
                secs = ((p.get("pm_audio") or {}).get(mk["k"], {}).get("qc") or {}).get("chunk_secs")
                times = [x / pm_slow for x in secs] if secs and len(secs) == len(cks) else \
                    [speak * len(c) / (sum(len(x) for x in cks) or 1) for c in cks]
                shown = 0.0
                for ci, (ck, csec) in enumerate(zip(cks, times)):
                    sents = sentences(ck, lang)
                    total_chars = sum(len(x) for x in sents) or 1
                    for si, sent in enumerate(sents):
                        d = csec * len(sent) / total_chars
                        add(f"pm-{mk['k']}-{ci}-{si}", lambda sent=sent: sl.caption(
                            lang, date, "prayer_meeting", L["service"], p["title"], sent, sl.BG_DIR / "기도.png"), d)
                        shown += d
                # 마디 끝을 시각표(pm_marks)에 맞춘다 — 반올림·여는 말 뒤 2초 쉼이 쌓여 다음 제목이 일찍 뜨던 것
                rest = (mk["end"] if not mk["k"].startswith("topic") else mk["speak_end"]) - mk["start"] - shown
                if seq and rest > 0:
                    last, sec = seq[-1]
                    seq[-1] = (last, sec + rest)
                if mk["k"].startswith("topic"):
                    add(f"pm-{mk['k']}-pray", lambda lead=lead: sl.caption(lang, date, "prayer_meeting", pray, p["title"],
                                                                         sentences(lead, lang),   # 세 문장 모두
                                                                         sl.BG_DIR / "기도.png"), mk["end"] - mk["speak_end"])
                used = mk["end"]
            if seq:
                last, sec = seq[-1]
                seq[-1] = (last, sec + max(0.0, sec_total - used))
            continue

        slow = bw.SPEED
        cks = bw.chunks(p["text"], lang)
        times = chunk_times(p, len(cks))
        used = 0.0
        verse_by_text = {re.sub(r"\W", "", v["text"])[:20]: v for v in s["verses"]}
        for ci, (ck, csec) in enumerate(zip(cks, times)):
            sents = sentences(ck, lang)
            total_chars = sum(len(x) for x in sents) or 1
            for si, sent in enumerate(sents):
                d = csec / slow * len(sent) / total_chars
                key = f"{t['id']}-{ci}-{si}"
                v = verse_by_text.get(re.sub(r"\W", "", sent)[:20]) if t["id"] == "reading" else None
                if v:
                    add(key, lambda v=v: sl.scripture(lang, date, v["reference"], re.sub(r"[()]", "", v["text"]),
                                                      sl.BG_DIR / "말씀.png"), d)
                elif t["id"] == "reading":
                    add(key, lambda sent=sent: sl.caption(lang, date, "reading", order_name["reading"], s["passage"],
                                                          sent, sl.BG_DIR / "말씀.png"), d)
                else:
                    head = p["title"] if t["id"] == "sermon" else order_name.get(t["id"], p["title"])
                    lab = L["sermon"] if t["id"] == "sermon" else L["service"]
                    add(key, lambda sent=sent, head=head, lab=lab: sl.caption(lang, date, t["id"], lab, head, sent,
                                                                             bgs.get(t["id"], bg_topic)), d)
                used += d
        # 끝 쉼(apad)·반올림 남은 시간은 마지막 화면을 늘린다
        if seq:
            last, sec = seq[-1]
            seq[-1] = (last, sec + max(0.0, sec_total - used))

    lst = folder / "frames.txt"
    with lst.open("w", encoding="utf-8") as f:
        for path, sec in seq:
            f.write(f"file '{path.resolve().as_posix()}'\nduration {sec:.3f}\n")
        f.write(f"file '{seq[-1][0].resolve().as_posix()}'\n")
    dst = folder / f"worship_{date}_{lang}.mp4"
    audio = ["-i", str(mp3)]
    afilter = ["-af", f"adelay={a.preroll * 1000}|{a.preroll * 1000}"] if a.preroll else []
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), *audio,
           "-map", "0:v", "-map", "1:a", *afilter, "-vf", f"fps={FPS},format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-g", str(FPS * 2),
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)
    print(f"영상 {dst.name} · 화면 {len(cache)}장 · {bw.dur(dst) / 60:.1f}분")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""예배 영상 완성 판정 — 통과하면 READY·READY.json, 아니면 FAILED.json 을 남긴다(송출 쪽은 READY 만 본다).

  python worship_verify.py <output/날짜_언어 폴더> [--preroll 300]

검사: mp4(20MB↑) · mp3 · script.json 의 모든 낭독 음성 · spec.json ·
      영상 H.264 1920x1080 30fps · 음성 AAC 48kHz · 키프레임 간격 ≤4초(-c copy 송출이라 그대로 나간다) ·
      길이 = 시간표 합계 + 대기 화면(preroll) ±3초.
종료 코드 0=통과, 1=실패. 표준 라이브러리 + ffprobe 만 쓴다.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

KST = dt.timezone(dt.timedelta(hours=9))


def probe(args: list[str]) -> str:
    r = subprocess.run(["ffprobe", "-v", "error", *args], capture_output=True, text=True)
    return r.stdout.strip()


def verify(folder: Path, preroll: int = 300) -> tuple[bool, dict]:
    why: list[str] = []
    info: dict = {"checked": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")}
    try:
        s = json.loads((folder / "script.json").read_text(encoding="utf-8"))
        date, lang = s["date"], s["lang"]
    except Exception as e:  # noqa: BLE001
        return False, {**info, "why": [f"script.json 읽기 실패({type(e).__name__})"]}
    info.update(date=date, lang=lang)
    mp4, mp3 = folder / f"worship_{date}_{lang}.mp4", folder / f"worship_{date}_{lang}.mp3"
    if not mp4.exists() or mp4.stat().st_size < 20_000_000:
        why.append("mp4 없음 또는 20MB 미만")
    if not mp3.exists() or mp3.stat().st_size < 1_000_000:
        why.append("mp3 없음")
    if not (folder / "spec.json").exists() or (folder / "spec.json").stat().st_size < 50:
        why.append("spec.json 없음")
    for p in s["parts"]:                                  # 낭독 음성이 빠진 순서가 없어야 한다(11-04 묶음 실패 재발 방지)
        if "text" in p and not p.get("audio"):
            why.append(f"{p['id']} 음성 경로 없음")
        for k, v in (p.get("pm_audio") or {}).items():
            if not v.get("audio"):
                why.append(f"{p['id']}.{k} 음성 경로 없음")
    if mp4.exists():
        v = probe(["-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height,r_frame_rate", "-of", "csv=p=0", str(mp4)]).split(",")
        a = probe(["-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate", "-of", "csv=p=0", str(mp4)]).split(",")
        if v[:4] != ["h264", "1920", "1080", "30/1"]:
            why.append(f"영상 형식 {','.join(v)} (h264 1920x1080 30fps 아님)")
        if a[:2] != ["aac", "48000"]:
            why.append(f"음성 형식 {','.join(a)} (aac 48kHz 아님)")
        dur = float(probe(["-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]) or 0)
        want = sum(t["sec"] for t in s.get("timeline", [])) + preroll
        info.update(duration_sec=round(dur, 1), expected_sec=round(want, 1), size_mb=round(mp4.stat().st_size / 1e6, 1))
        if abs(dur - want) > 3:
            why.append(f"길이 {dur:.1f}초 ≠ 시간표+대기 {want:.1f}초")
        kf = [float(x) for x in probe(["-select_streams", "v:0", "-skip_frame", "nokey", "-show_entries", "frame=pts_time",
                                       "-of", "csv=p=0", str(mp4)]).split() if x]
        gaps = [b - a for a, b in zip(kf, kf[1:])] + ([dur - kf[-1]] if kf else [])
        info["max_keyframe_gap_sec"] = round(max(gaps), 2) if gaps else None
        if not gaps or max(gaps) > 4.0:
            why.append(f"키프레임 간격 최대 {max(gaps) if gaps else '?'}초 (4초 초과)")
    for f in ("READY", "READY.json", "FAILED.json"):
        (folder / f).unlink(missing_ok=True)
    if why:
        (folder / "FAILED.json").write_text(json.dumps({**info, "why": why}, ensure_ascii=False, indent=1), encoding="utf-8")
        return False, {**info, "why": why}
    (folder / "READY.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "READY").write_text(f"{date} {lang} {info['checked']}\n", encoding="utf-8")
    return True, info


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    pre = int(sys.argv[sys.argv.index("--preroll") + 1]) if "--preroll" in sys.argv else 300
    ok, res = verify(Path(sys.argv[1]), pre)
    print(("통과" if ok else "실패") + " " + json.dumps(res, ensure_ascii=False))
    sys.exit(0 if ok else 1)

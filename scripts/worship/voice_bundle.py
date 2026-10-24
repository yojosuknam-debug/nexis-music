"""
목소리 묶음 — 맥미니(원고·목소리) → 미니PC(조립·방송). docs/worship-order.md '나눠 맡기'.

    python scripts/worship/voice_bundle.py pack   <맥 output/날짜_언어> <outbox/worship-voice/날짜_언어>
    python scripts/worship/voice_bundle.py find   <미니PC /mnt/external/macmini> <날짜_언어>      # 가장 최근 묶음 경로
    python scripts/worship/voice_bundle.py unpack <묶음 폴더> <미니PC output/날짜_언어>

묶음 = script.json(오디오 경로를 파일 이름만으로) + 낭독 wav 들 + bundle.json(목록·만든 시각).
찬송·연주곡은 넣지 않는다 — 미니PC 가 음악 대장(music.json)대로 내려받는다. 자막 시각표(qc.chunk_secs)는 script.json 에 그대로 간다.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path


def pack(out: Path, dest: Path) -> None:
    s = json.loads((out / "script.json").read_text(encoding="utf-8"))
    dest.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

    def take(path: str) -> str:
        src = Path(path)
        name = src.name if src.parent == out else f"cache_{src.name}"   # 주기도문·축복 저장본은 cache/ 에 있다
        shutil.copy(src, dest / name)   # 시각을 새로 — 옛 시각(저장본)이면 이관이 먼저 옮겨 묶음이 둘로 갈렸다(10-24)
        files.append(name)
        return name

    for p in s["parts"]:
        if "song" in p:
            p.pop("audio", None)
        elif "pm" in p:
            for v in p["pm_audio"].values():
                v["audio"] = take(v["audio"])
            for k in ("audio", "pm_marks"):
                p.pop(k, None)
        elif p.get("audio"):
            p["audio"] = take(p["audio"])
        else:
            sys.exit(f"{p['id']}: 목소리 파일이 없다 — --voice 가 끝까지 돌았는지 확인")
    for k in ("timeline", "total_sec"):
        s.pop(k, None)
    (dest / "script.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    (dest / "bundle.json").write_text(json.dumps(
        {"date": s["date"], "lang": s["lang"], "files": files + ["script.json"],
         "made": dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"묶음 {dest} · 파일 {len(files) + 1}개")


def find(root: Path, key: str) -> Path:
    """자동 이관은 묶음마다 날짜 폴더(YYYY-MM-DD_HHMMSS)에 넣는다 → 가장 최근 것."""
    hits = sorted(root.glob(f"*/worship-voice/{key}/bundle.json"))
    if not hits:
        sys.exit(f"{key} 목소리 묶음이 {root} 에 아직 없다")
    return hits[-1].parent


def locate(src: Path, meta: dict) -> dict[str, Path]:
    """묶음 파일 위치. 이관이 나눠 옮긴 경우 같은 묶음의 다른 이관 폴더(만든 시각 이후 것)에서도 찾는다."""
    made = dt.datetime.fromisoformat(meta["made"]).strftime("%Y-%m-%d_%H%M%S")
    sibs = [d for d in sorted(src.parent.parent.parent.glob(f"*/worship-voice/{src.name}"), reverse=True)
            if d != src and d.parent.parent.name >= made]
    where = {}
    for f in meta["files"]:
        where[f] = next((d / f for d in [src, *sibs] if (d / f).exists()), None)
    return where


def unpack(src: Path, out: Path) -> None:
    meta = json.loads((src / "bundle.json").read_text(encoding="utf-8"))
    where = locate(src, meta)
    missing = [f for f, w in where.items() if w is None]
    if missing:
        sys.exit(f"묶음이 덜 왔다: {missing[:5]}")
    out.mkdir(parents=True, exist_ok=True)
    for f, w in where.items():
        shutil.copy2(w, out / f)
    print(f"풀기 {out} · 파일 {len(meta['files'])}개 (맥 제작 {meta['made']})")


def main() -> int:
    cmd, a, b = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    if cmd == "pack":
        pack(a, Path(b))
    elif cmd == "find":
        print(find(a, b))
    elif cmd == "unpack":
        unpack(a, Path(b))
    return 0


if __name__ == "__main__":
    sys.exit(main())

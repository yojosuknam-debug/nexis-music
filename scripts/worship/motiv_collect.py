"""
미니PC 외장하드 정리 — 맥미니 이관 폴더(/mnt/external/macmini/<시각>/motiv/<id>/)에 흩어진 동기부여 영상을
/mnt/external/nexis-motiv/ 한곳에 모으고 목록을 만든다(10-25 사용자). 미니PC 에서 실행, 여러 번 돌려도 된다.

    python3 motiv_collect.py [--dry-run]

nexis-motiv/
  영상/m0001_<제목>.mp4      편마다 최신본 하나(다시 만든 편은 새것)
  원고/m0001.json            원고·길이·발음 오류·배경
  이전본/m0001_<이관 시각>.mp4  새것으로 바뀐 옛 영상(지우지 않고 둔다)
  목록.md · 목록.csv         한눈에 보는 표(csv 는 엑셀용)
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from pathlib import Path

SRC = Path("/mnt/external/macmini")
DST = Path("/mnt/external/nexis-motiv")


def safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "", s).strip()[:40]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vid, txt, old = DST / "영상", DST / "원고", DST / "이전본"
    for d in (vid, txt, old):
        d.mkdir(parents=True, exist_ok=True)

    def mv(src: Path, dst: Path) -> None:
        print(f"  {src} → {dst}")
        if not a.dry_run:
            shutil.move(str(src), str(dst))

    # 새로 들어온 것: 이관 시각 순서대로(늦게 온 것이 최신본)
    arrived = sorted(SRC.glob("*/motiv/m*/script.json"), key=lambda p: p.parts[-4])
    for sj in arrived:
        folder, stamp = sj.parent, sj.parts[-4]
        mp4s = list(folder.glob("*.mp4"))
        if not mp4s:                                # 영상이 아직 다른 이관 묶음에 있으면 다음 번에
            continue
        meta = json.loads(sj.read_text(encoding="utf-8"))
        mid = meta["id"]
        for cur in vid.glob(f"{mid}_*.mp4"):        # 이미 있는 편 → 옛 것은 이전본으로
            prev = json.loads((txt / f"{mid}.json").read_text(encoding="utf-8")) if (txt / f"{mid}.json").exists() else {}
            mv(cur, old / f"{mid}_{prev.get('arrived', 'before')}.mp4")
        meta["arrived"] = stamp
        print(f"{mid} ({stamp})")
        mv(mp4s[0], vid / f"{mid}_{safe(meta['title'])}.mp4")
        if not a.dry_run:
            (txt / f"{mid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            sj.unlink()
            for d in (folder, folder.parent, folder.parent.parent):   # 빈 폴더만 지운다
                try:
                    d.rmdir()
                except OSError:
                    break

    rows = []
    for f in sorted(txt.glob("m*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        v = next(vid.glob(f"{m['id']}_*.mp4"), None)
        rows.append({"번호": m["id"], "주제": m["theme"], "제목": m["title"], "하루 한 줄": m["line"],
                     "길이(초)": m.get("sec", ""), "발음 오류": f"{m.get('max_err', 0):.0%}",
                     "다시 만듦": "예" if m.get("redo") else "", "배경": m.get("bg", "단색"),
                     "영상": v.name if v else "(없음)", "들어온 시각": m.get("arrived", "")})
    if a.dry_run:
        print(f"(시험) {len(rows)}편")
        return 0
    with (DST / "목록.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["번호"])
        w.writeheader()
        w.writerows(rows)
    themes: dict[str, int] = {}
    for r in rows:
        themes[r["주제"]] = themes.get(r["주제"], 0) + 1
    check = [r["번호"] for r in rows if int(r["발음 오류"].rstrip("%")) > 12]
    md = ["# 동기부여 쇼츠 목록 (nexis-motiv · 하루 한 줄, 동기부여)", "",
          f"- 모두 **{len(rows)}편** · 업로드 안 함 · 목소리 = 내 목소리(AI 합성)",
          "- 주제별: " + " · ".join(f"{k} {n}" for k, n in sorted(themes.items(), key=lambda x: -x[1])),
          f"- 들어 보고 확인할 편(발음 오류 12% 초과): {', '.join(check) if check else '없음'}",
          f"- 이전본(다시 만들어 바뀐 옛 영상): {len(list(old.glob('*.mp4')))}개 — `이전본/`", "",
          "| 번호 | 주제 | 제목 | 하루 한 줄 | 길이 | 발음 오류 | 다시 만듦 | 배경 |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['번호']} | {r['주제']} | {r['제목']} | {r['하루 한 줄']} | {r['길이(초)']}초 | {r['발음 오류']} | "
           f"{r['다시 만듦']} | {r['배경']} |" for r in rows]
    (DST / "목록.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"정리 끝 — 영상 {len(rows)}편 · 이전본 {len(list(old.glob('*.mp4')))}개 → {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

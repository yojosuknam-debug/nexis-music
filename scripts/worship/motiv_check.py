"""
동기부여 원고 은행 검사 — docs/motiv-bank.md 의 형식·길이·금지어·중복을 본다. 하나라도 걸리면 종료 코드 1.

    python scripts/worship/motiv_check.py data/motiv/*.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BANNED = ["포기하지 마", "할 수 있어요", "할 수 있습니다", "꿈을 향해", "최고의 나", "여러분", "화이팅", "파이팅",
          "성공의 비결", "부자", "명언", "말했습니다", "라고 했", "연구에 따르면", "통계", "퍼센트", "반드시 성공"]
BAD_CHARS = re.compile(r"[0-9A-Za-z\"'“”‘’()\[\]{}<>~…·]|[\U0001F300-\U0001FAFF☀-➿]")
SIM = 0.42   # 풀어 주는 말 글자 3-gram 겹침이 이보다 크면 중복으로 본다


def sents(t: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+", t.strip()) if s.strip()]


def grams(t: str) -> set[str]:
    t = re.sub(r"[^가-힣]", "", t)
    return {t[i:i + 3] for i in range(len(t) - 2)}


def check(m: dict) -> list[str]:
    err = []
    for k in ("id", "theme", "title", "line", "body", "close"):
        if not str(m.get(k, "")).strip():
            err.append(f"{k} 없음")
    if err:
        return err
    if not re.fullmatch(r"m\d{4}", m["id"]):
        err.append("id 형식(m0001)")
    if len(m["title"]) > 25:
        err.append(f"title {len(m['title'])}자 > 25")
    if not 12 <= len(m["line"]) <= 24:
        err.append(f"line {len(m['line'])}자 (12~24)")
    if len(m["close"]) > 30:
        err.append(f"close {len(m['close'])}자 > 30")
    ss = sents(m["body"])
    if not 5 <= len(ss) <= 7:
        err.append(f"body {len(ss)}문장 (5~7)")
    for s in ss:
        if not 12 <= len(s) <= 32:
            err.append(f"body 문장 {len(s)}자 (12~32): {s}")
    for k in ("line", "body", "close"):
        for s in sents(m[k]):
            if s[-1] not in ".?":
                err.append(f"{k} 문장 끝 부호: {s}")
        if BAD_CHARS.search(m[k]):
            err.append(f"{k} 금지 문자: {BAD_CHARS.findall(m[k])}")
    whole = " ".join(m[k] for k in ("title", "line", "body", "close"))
    err += [f"상투어 '{b}'" for b in BANNED if b in whole]
    return err


def main(paths: list[str]) -> int:
    items = []
    for p in paths:
        for n, ln in enumerate(Path(p).read_text(encoding="utf-8-sig").splitlines(), 1):
            if ln.strip():
                try:
                    items.append((f"{Path(p).name}:{n}", json.loads(ln)))
                except json.JSONDecodeError as e:
                    print(f"{Path(p).name}:{n} JSON 오류 {e}")
                    return 1
    bad, ids, lines, gs = 0, {}, {}, []
    for where, m in items:
        err = check(m)
        if m.get("id") in ids:
            err.append(f"id 중복({ids[m['id']]})")
        ids.setdefault(m.get("id"), where)
        key = re.sub(r"[^가-힣]", "", m.get("line", ""))
        if key in lines:
            err.append(f"하루 한 줄 중복({lines[key]})")
        lines.setdefault(key, where)
        g = grams(m.get("body", ""))
        for w2, g2 in gs:
            if g and g2 and len(g & g2) / len(g | g2) > SIM:
                err.append(f"풀어 주는 말이 {w2} 와 비슷함")
        gs.append((where, g))
        if err:
            bad += 1
            print(f"✗ {where} {m.get('id')} — " + " / ".join(err))
    themes = {}
    for _, m in items:
        themes[m.get("theme")] = themes.get(m.get("theme"), 0) + 1
    print(f"{len(items)}편 · 통과 {len(items) - bad} · 걸림 {bad} · 주제 {len(themes)}가지")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

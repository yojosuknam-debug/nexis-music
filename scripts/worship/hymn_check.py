"""
자작 찬송가 가사 검사기 — 음절(율격)·절 구조·인칭·발음 무게·피할 표현. 무료(규칙 기반).
근거: docs/research/2026-10-24_찬송가-작법-선정기준.md (AI 가 쓴 가사는 음절 표기가 자주 틀린다 — 실측)

    python scripts/worship/hymn_check.py 가사.txt [--meter 8.8.8.8]
    (Suno 가사 형식 그대로 넣어도 된다: [Verse 1] 태그·[End]·(괄호) 무시, 절은 태그나 빈 줄로 나눔)

종료 코드: 0 통과 · 1 고칠 것 있음(음절·행 수 불일치)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PARTICLE_END = ("은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "로", "에게", "에서", "부터", "까지")
FIRST_SING = re.compile(r"(^|\s)(나|내|나의|나를|나는|내가|내게|저|제가|저를|저의)(\s|$)")
FIRST_PLUR = re.compile(r"우리")
AVOID = ["모든 병", "반드시 부", "성공", "번영", "부자 되", "축복만", "무조건", "결코 아프지"]
METERS = {"S.M.": "6.6.8.6", "C.M.": "8.6.8.6", "L.M.": "8.8.8.8"}


def stanzas(text: str) -> list[list[str]]:
    out, cur = [], []
    for raw in text.splitlines():
        ln = raw.strip()
        if re.match(r"^\[(verse|stanza|절|final)[^\]]*\]$", ln, re.I) or not ln:
            if cur:
                out.append(cur)
                cur = []
            continue
        if re.match(r"^\[.*\]$", ln) or ln.startswith("@"):      # [End]·[Intro]·'@0:12' 시각 줄
            continue
        ln = re.sub(r"\(.*?\)", "", ln).strip()
        if ln:
            cur.append(ln)
    if cur:
        out.append(cur)
    return out


def syllables(line: str) -> int:
    ko = len(re.findall(r"[가-힣]", line))
    if ko:
        return ko
    words = re.findall(r"[a-z']+", line.lower())                 # 영어: 모음 묶음 근사
    return sum(max(1, len(re.findall(r"[aeiouy]+", w)) - (1 if w.endswith("e") and len(w) > 2 else 0))
               for w in words)


def heavy(line: str) -> float:
    """받침 있는 음절 비율 — 높으면 노래하기 무겁다."""
    s = re.findall(r"[가-힣]", line)
    return sum(1 for c in s if (ord(c) - 0xAC00) % 28) / len(s) if s else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--meter", help="예: 8.8.8.8 · 8.7.8.7 · C.M. · L.M. · S.M.")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8")
    st = stanzas(text)
    if not st:
        print("가사를 찾지 못했다")
        return 1
    want = METERS.get(a.meter, a.meter) if a.meter else ".".join(str(syllables(x)) for x in st[0])
    target = [int(x) for x in want.split(".")]
    errors, notes = [], []
    print(f"절 {len(st)}개 · 목표 율격 {want}" + ("" if a.meter else " (1절에서 추정)"))
    for i, lines in enumerate(st, 1):
        counts = [syllables(x) for x in lines]
        mark = "✅" if counts == target else "❌"
        print(f"{mark} {i}절 {'.'.join(map(str, counts))}")
        if len(lines) != len(target):
            errors.append(f"{i}절: {len(lines)}행 (목표 {len(target)}행)")
        for j, (ln, c) in enumerate(zip(lines, counts)):
            if j < len(target) and c != target[j]:
                errors.append(f"{i}절 {j + 1}행 {c}음절(목표 {target[j]}): {ln}")
            if ln.rstrip(" ,.!?").endswith(PARTICLE_END):
                notes.append(f"{i}절 {j + 1}행 조사로 끝남(긴 음에 조사가 걸리면 어색): {ln}")
            if heavy(ln) > 0.7:
                notes.append(f"{i}절 {j + 1}행 받침이 많음({heavy(ln):.0%}) — 소리 내어 불러 보기: {ln}")
    body = " ".join(" ".join(x) for x in st)
    if FIRST_SING.search(body) and FIRST_PLUR.search(body):
        notes.append("'나'와 '우리'가 섞임 — 곡 안에서 시점이 흔들리지 않는지 확인")
    for w in AVOID:
        if w in body:
            notes.append(f"피할 표현 후보 '{w}' — 성경 근거 없는 약속이 아닌지 확인")
    if not 2 <= len(st) <= 4:
        notes.append(f"절이 {len(st)}개 — 규격은 3절 기본, 2~4절")
    for e in errors:
        print("  ❌ " + e)
    for n in notes:
        print("  ⚠️ " + n)
    print("통과" if not errors else f"고칠 것 {len(errors)}개")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

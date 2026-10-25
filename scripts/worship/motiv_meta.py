"""
동기부여 쇼츠 유튜브 제목·설명·태그 만들기 — 원고 은행(data/motiv/2026-*.jsonl) + 편마다 쓴 제목·첫 문장(data/motiv/hooks.jsonl)
→ 편마다 meta JSON(motiv_publish.py 가 읽는 형식). 주제별 해시태그·태그는 아래 표.

    python scripts/worship/motiv_meta.py <출력 폴더>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data" / "motiv"
TAGS = {   # 주제 → (해시태그 앞 두 개 — 설명 위에 노출, 태그)
    "시작": (["#동기부여", "#새로운시작"], ["새로운 시작", "아침 동기부여", "월요병", "작심삼일"]),
    "지침": (["#위로", "#힘들때"], ["위로", "힘들 때 듣는 말", "번아웃", "직장인 위로"]),
    "실패 뒤": (["#위로", "#다시시작"], ["실패", "다시 시작", "불합격", "실수"]),
    "비교": (["#자존감", "#비교하지마"], ["자존감", "비교", "남과 비교", "인생 속도"]),
    "관계": (["#인간관계", "#위로"], ["인간관계", "관계 고민", "사과", "외로움"]),
    "습관": (["#좋은습관", "#자기계발"], ["습관", "좋은 습관", "미라클모닝", "루틴"]),
    "공부와 시험": (["#공부자극", "#공부동기부여"], ["공부자극", "공부 동기부여", "수험생", "시험"]),
    "돈과 일": (["#직장인", "#동기부여"], ["직장인", "직장인 동기부여", "이직", "월급"]),
    "몸과 마음": (["#마음챙김", "#힐링"], ["마음챙김", "불안", "힐링", "멘탈 관리"]),
    "작은 기쁨": (["#힐링", "#소확행"], ["소확행", "힐링", "감사", "행복"]),
}
BASE_TAGS = ["동기부여", "하루한줄", "좋은글", "자기계발", "위로", "shorts"]


def build(m: dict, h: dict) -> dict:
    head, tags = TAGS.get(m["theme"], (["#동기부여", "#위로"], []))
    hashtags = " ".join(dict.fromkeys(head + ["#동기부여", "#하루한줄", "#좋은글", "#shorts"]))
    desc = (f"{h['hook']}\n\n오늘의 한 줄: {m['line']}\n오늘 해 볼 것: {m['close']}\n\n"
            "매일 아침 마음을 다잡는 하루 한 줄을 올립니다. 구독하고 내일도 함께해요.\n\n"
            f"※ 목소리는 AI로 합성했습니다.\n\n{hashtags}")
    return {"title": f"{h['title']} #shorts"[:100], "description": desc,
            "tags": list(dict.fromkeys(tags + BASE_TAGS + [m["theme"]]))}


def main(out: str) -> int:
    bank = {m["id"]: m for f in sorted(DATA.glob("2026-*.jsonl"))
            for m in map(json.loads, filter(str.strip, f.read_text(encoding="utf-8-sig").splitlines()))}
    hooks = {h["id"]: h for h in map(json.loads, filter(str.strip, (DATA / "hooks.jsonl").read_text(encoding="utf-8").splitlines()))}
    o = Path(out)
    o.mkdir(parents=True, exist_ok=True)
    for mid, h in hooks.items():
        (o / f"{mid}.json").write_text(json.dumps(build(bank[mid], h), ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sorted(set(bank) - set(hooks))
    print(f"메타 {len(hooks)}편 → {o}" + (f" · 제목 없는 편 {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

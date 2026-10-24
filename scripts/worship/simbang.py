"""
심방 말씀 한 편 — 작은 방에 둘러앉은 소모임에서 목사님이 조곤조곤 나누는 말씀. 찬양·주기도문·화면 없이 목소리만(mp3).
큐티 자료(build_worship 과 같은 순서표) → 대화체 원고(Gemini) → 내 목소리(Chatterbox·목소리 E) → mp3.

    WORSHIP_QT_DATA=… WORSHIP_QT_ELIGIBLE=… python scripts/worship/simbang.py --date 2026-10-25

순서: 인사 → 본문 봉독 → 말씀 → 기도. 낭독 방식·음량 처리는 build_worship 과 같다(한 문장씩·0.8초 쉼·8% 느리게).
송출용이 아니라 들어 보는 용도(10-24 사용자: 곡이 없어 송출은 아직 무리).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import build_worship as bw

PROMPT = """당신은 작은 교회의 따뜻하고 담백한 목사님입니다. 지금 성도의 집 작은 방에서 대여섯 명이 둘러앉은 심방 자리입니다.
강단 설교가 아니라 가까이 마주 앉아 조곤조곤 이야기하듯, 아래 오늘의 큐티 자료로 나눌 말씀 원고를 씁니다.
반드시 JSON 하나만 출력하세요.

{{"greeting": "인사 — 3~4문장. 이렇게 모여 앉은 자리에 대한 고마움, 편안하게 말씀을 나누자는 초대",
  "sermon": "말씀 — 1,800~2,100자. 본문 한두 구절을 천천히 되짚고, 듣는 이에게 질문을 던져 잠시 생각하게 하고, 일상의 작은 예화 하나, 오늘 삶에서 해 볼 한 가지로 맺음",
  "prayer": "마무리 기도 — 250~350자. 이 자리에 모인 이들과 그 가정을 위한 기도, '예수님의 이름으로 기도합니다. 아멘.'으로 끝"}}

규칙:
- 소리 내어 읽을 글입니다. 괄호·따옴표·번호표·'첫째:' 같은 표기·이모지를 쓰지 말고 말로 풀어 쓰세요.
- 숫자는 아라비아 숫자를 쓰지 말고 한글로 쓰세요. 성경 장절 표기(4:13 등)는 쓰지 마세요.
- 오늘 본문 말고 다른 성경 구절을 직접 인용하지 마세요(틀린 인용 방지).
- 큰 소리로 외치는 말투, 과장된 감탄, 설교 상투어, 교단·정치·헌금 이야기를 피하세요. 낮고 다정하게.
- '여러분' 대신 '우리'를 자주 쓰고, 문장은 짧게(한 문장 40자 안팎, 길어도 60자 이내 — 긴 문장은 낭독이 갑자기 빨라진다).

제목: {title}
본문: {ref}
{verses}
요약: {summary}
말씀Log 설교 초안: {sermon}
묵상: {meditation}
적용: {application}"""

GAP_PART = 1.2   # 순서 사이 쉼(초)


def make_script(day: dt.date, out: Path) -> dict:
    qt = bw.qt_from_data(day)
    verses = "\n".join(f"{v['reference']} {v['text']}" for v in qt["verses"])
    g = bw.gemini_json(bw.env()["GEMINI_API_KEY"], PROMPT.format(
        title=qt["title"], ref=qt["passageReference"], verses=verses, summary=qt["summary"], sermon=qt["sermon"],
        meditation=qt["meditation"], application=" ".join(qt["application"])))
    reading = (f"함께 읽을 말씀은 {bw.speak_ref(qt['passageReference'], 'ko')} 말씀입니다. "
               + ". ".join(bw.clean_speech(v["text"]).rstrip(".") for v in qt["verses"]) + ".")
    script = {"date": day.isoformat(), "kind": "simbang", "qt_id": qt["id"], "title": qt["title"],
              "passage": qt["passageReference"], "parts": [
                  {"id": "greeting", "title": "인사", "text": bw.clean_speech(g["greeting"])},
                  {"id": "reading", "title": "본문", "text": reading, "verbatim": True},
                  {"id": "sermon", "title": qt["title"], "text": bw.clean_speech(g["sermon"])},
                  {"id": "prayer", "title": "기도", "text": bw.clean_speech(g["prayer"])}]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    bw.log(f"원고 {sum(len(p['text']) for p in script['parts'])}자 · {qt['passageReference']} {qt['title']}")
    return script


def join(script: dict, out: Path) -> Path:
    """build_worship.mix 와 같은 처리(8% 느리게·고정 음량·리미터·20ms 페이드), 찬양 없이 순서 사이 GAP_PART 초."""
    inputs, filters, t = [], [], 0.0
    for i, p in enumerate(script["parts"]):
        f = Path(p["audio"])
        body = bw.dur(f) / bw.SPEED
        gain = max(-20.0, min(20.0, -16.0 - bw.loudness(f)))
        inputs += ["-i", str(f)]
        filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,adeclick,atempo={bw.SPEED},"
                       f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=disabled,"
                       f"afade=t=in:d=0.02,afade=t=out:st={max(0.0, body - 0.02):.3f}:d=0.02,"
                       f"apad=pad_dur={GAP_PART}[a{i}]")
        p["start"] = round(t, 1)
        t += body + GAP_PART
    n = len(script["parts"])
    dst = out / f"simbang_{script['date']}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                    ";".join(filters + ["".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"]),
                    "-map", "[out]", "-b:a", "160k", str(dst)], check=True)
    script["total_sec"] = round(t, 1)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    bw.log(f"완성 {dst.name} · {t / 60:.1f}분 — " + " · ".join(
        f"{int(p['start'] // 60):02d}:{int(p['start'] % 60):02d} {p['title']}" for p in script["parts"]))
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    if not bw.QT_DATA:
        sys.exit("WORSHIP_QT_DATA 가 필요하다(큐티 자료 경로)")
    day = dt.date.fromisoformat(a.date)
    out = bw.OUT / "simbang" / a.date
    sp = out / "script.json"
    script = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else make_script(day, out)
    v = bw.Voice("ko")
    for p in script["parts"]:
        info = v.part(p["text"], out / f"{p['id']}.wav")
        p["audio"], p["qc"] = str(out / f"{p['id']}.wav"), info
        bw.log(f"{p['title']}: {info['sec']:.0f}초 · 최대 오류 {info['max_err']:.0%} · GPU {info['gpu_gb']}GB")
    join(script, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

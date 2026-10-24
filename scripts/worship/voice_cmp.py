"""
목소리·규칙 비교 샘플 — 같은 대본(질문 포함 약 1분)을 지금 환경변수 설정으로 읽어 mp3 로. docs/voice-onboarding.md 3단계.

    WORSHIP_REF_KO=<참조.wav> python scripts/worship/voice_cmp.py <out.mp3> [대본.txt]

대본을 안 주면 최근 심방 말씀(output/simbang/*/script.json)의 말씀 앞부분, 그것도 없으면 아래 기본 대본.
비교할 때는 바꾸려는 것 하나만 바꾼다(WORSHIP_REF_KO / WORSHIP_CHUNK=para / WORSHIP_TUNE=1 …).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import json
from pathlib import Path

import build_worship as bw

DEFAULT = ("사랑하는 여러분. 오늘도 조용히 마음을 모으고 말씀에 귀를 기울여 봅니다. 뜻대로 되지 않는 날에도 우리는 혼자가 아닙니다. "
           "우리는 무엇을 가장 사랑하며 살고 있을까요? 잠시 생각해 보세요. 그것은 바로 우리를 먼저 사랑하신 하나님의 마음입니다. "
           "오늘 본문은 민수기 6장 24절에서 26절 말씀입니다. 작은 기쁨을 알아차리고 곁에 있는 사람에게 따뜻한 말을 건네면 좋겠습니다.")


def script_text() -> str:
    if len(sys.argv) > 2:
        return Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    for sp in sorted((bw.OUT / "simbang").glob("*/script.json")):
        sermon = next((p["text"] for p in json.loads(sp.read_text(encoding="utf-8"))["parts"]
                       if p["id"] == "sermon"), "")
        text = ""
        for x in (s for s in re.split(r"(?<=[.!?])\s+", sermon) if s.strip()):
            text = f"{text} {x}".strip()
            if len(text) > 300 and "?" in text:
                return text
    return DEFAULT


def main() -> int:
    out = Path(sys.argv[1])
    work = out.parent / out.stem                  # 문장 저장본(_chunks)은 샘플마다 따로
    work.mkdir(parents=True, exist_ok=True)
    wav = work / "voice.wav"
    info = bw.Voice("ko").part(script_text(), wav)
    body = bw.dur(wav) / bw.SPEED
    gain = max(-20.0, min(20.0, -16.0 - bw.loudness(wav)))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af",
                    f"aresample=44100,atempo={bw.SPEED},volume={gain:.2f}dB,"
                    f"alimiter=limit=0.84:attack=5:release=80:level=disabled,"
                    f"afade=t=out:st={max(0.0, body - 0.05):.3f}:d=0.05", "-b:a", "160k", str(out)], check=True)
    print(f"RESULT {out.name} {body:.1f}초 묶음 {info['chunks']} 최대오류 {info['max_err']:.0%} GPU {info['gpu_gb']}GB "
          f"다시띄움 {os.environ.get('WORSHIP_RESTARTS', '0')}번 | 참조 {bw.REF['ko']} TUNE={bw.TUNE} PARA={bw.PARA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
예배 설교 목소리 비교 샘플 — 같은 문단을 여러 엔진·목소리로 읽혀 A/B/C/D mp3 로 만든다.

    python scripts/worship/voice_samples.py OUT_DIR

키는 레포 루트 .env.local(sync-env.ps1 nexis-music 로 생성)에서 읽고 출력하지 않는다.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TEXT = (
    "사랑하는 성도 여러분, 우리는 모두 삶 속에서 갈증을 느낍니다. "
    "때로는 물질적인 것에 대한 갈증이요, 때로는 인정과 사랑에 대한 갈증입니다. "
    "그러나 아무리 채워도 다시 목마르게 되는 세상의 물처럼, 이러한 갈증은 끊임없이 우리를 지치게 합니다. "
    "오늘 본문에서 예수님은 사마리아 여인에게, 영원히 목마르지 않는 생수에 대해 말씀하십니다. "
    "예수께서 대답하여 가라사대, 이 물을 먹는 자마다 다시 목마르려니와, "
    "내가 주는 물을 먹는 자는 영원히 목마르지 아니하리니, "
    "나의 주는 물은 그 속에서 영생하도록 솟아나는 샘물이 되리라."
)
STYLE = ("작은 교회의 따뜻하고 차분한 목회자가 성도들에게 설교하듯 읽어 주세요. "
         "서두르지 말고, 문장 사이에 여유 있게 쉬며, 성경 구절은 조금 더 천천히 또박또박 낭독하세요.")

# Gemini 3.x TTS 는 앞의 한국어 지시문까지 소리 내어 읽었다(10-22 Whisper 대조) → 공식 예시처럼 "말투: 본문" 한 줄 형식
STYLE_GEMINI = ("Read aloud the following Korean sermon in the warm, calm, unhurried voice of a small-church pastor, "
                "pausing gently between sentences and reading the Bible verses a little more slowly")

SAMPLES = [
    ("A", "gemini", "gemini-3.8-flash-tts", "Gacrux"),
    ("B", "gemini", "gemini-2.5-pro-preview-tts", "Charon"),
    ("C", "gemini", "gemini-2.5-pro-preview-tts", "Sulafat"),
    ("D", "openai", "gpt-4o-mini-tts-2025-12-15", "cedar"),
]


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def post(url: str, headers: dict, body: dict) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def gemini(key: str, model: str, voice: str) -> tuple[bytes, str]:
    body = {
        "contents": [{"parts": [{"text": f"{STYLE_GEMINI}: {TEXT}"}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
    }
    d = json.loads(post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        {"x-goog-api-key": key}, body))
    part = d["candidates"][0]["content"]["parts"][0]["inlineData"]
    return base64.b64decode(part["data"]), part.get("mimeType", "")


def openai(key: str, model: str, voice: str) -> bytes:
    return post("https://api.openai.com/v1/audio/speech", {"Authorization": f"Bearer {key}"},
                {"model": model, "voice": voice, "input": TEXT, "instructions": STYLE, "response_format": "mp3"})


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    e = env()
    for label, engine, model, voice in SAMPLES:
        dst = out / f"목소리_{label}.mp3"
        try:
            if engine == "gemini":
                pcm, mime = gemini(e["GEMINI_API_KEY"], model, voice)
                rate = 24000
                if "rate=" in mime:
                    rate = int(mime.split("rate=")[1].split(";")[0])
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1",
                                "-i", "pipe:0", "-b:a", "128k", str(dst)], input=pcm, check=True)
            else:
                dst.write_bytes(openai(e["OPENAI_API_KEY"], model, voice))
            print(label, "OK", model, voice)
        except urllib.error.HTTPError as err:
            print(label, "실패", model, voice, err.code, err.read()[:300].decode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

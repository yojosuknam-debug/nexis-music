"""
동기부여 쇼츠 한 편(nexis-motiv '하루 한 줄, 동기부여') — 원고(Gemini) → 내 목소리(Chatterbox·예배와 같은 B 목소리) → 세로 1080×1920 mp4.
업로드는 하지 않는다(10-25 사용자: 시범 영상만). 결과는 MOTIV_OUT/<날짜>_<번호>/ 에 둔다.

    WORSHIP_REF_DIR=… WORSHIP_DEVICE=mps python motiv.py [--theme "월요일 아침"] [--date 2026-10-25]

순서: 하루 한 줄(크게) → 풀어 주는 말(문장 자막) → 맺는 한 문장. 낭독 방식은 build_worship 과 같다(한 문장씩·자연스러운 쉼).
명언은 넣지 않는다 — 실제로 한 말인지 확인이 안 되면 틀린 말을 내 목소리로 하게 된다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

W = Path(os.environ.get("WORSHIP_DIR", Path(__file__).resolve().parent))   # 맥미니는 레포 밖에 두고 레포의 worship 폴더를 가리킨다
sys.path.insert(0, str(W))
import build_worship as bw  # noqa: E402
import slides as sl  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

OUT = Path(os.environ.get("MOTIV_OUT", Path.home() / "Work" / "nexis-motiv" / "output"))
OUTBOX = Path(os.environ.get("MOTIV_OUTBOX", Path.home() / "Work" / "outbox" / "motiv"))   # archive-outbox 가 미니PC 로 옮긴다
SPEED = float(os.environ.get("MOTIV_SPEED", "0.95"))   # 예배(0.92)보다 조금 힘 있게
HEAD, TAIL = 0.5, 1.5        # 앞뒤 여백(초) — 끝은 맺는 문장을 잠시 띄워 둔다
VW, VH, FPS = 1080, 1920, 30
CHANNEL = "하루 한 줄, 동기부여"
AI_NOTE = "목소리는 AI로 합성했습니다"
GOLD, WHITE, DIM = (232, 196, 120), (245, 242, 236), (160, 156, 148)

PROMPT = """당신은 유튜브 쇼츠 채널 '하루 한 줄, 동기부여'의 원고 작가입니다. 담담하고 진심 어린 30~40대 목소리로 읽힐 50~60초 원고를 씁니다.
반드시 JSON 하나만 출력하세요.

{{"title": "유튜브 제목 — 25자 이내, 듣는 사람의 상황이 보이게",
  "line": "하루 한 줄 — 화면에 크게 뜰 한 문장, 12~24자",
  "body": "풀어 주는 말 — 5~7문장, 한 문장 15~30자. 구체적인 장면 하나(시간·장소·행동)로 시작해 마음의 전환으로",
  "close": "맺는 한 문장 — 오늘 당장 해 볼 아주 작은 행동 하나, 30자 이내"}}

규칙:
- 소리 내어 읽을 글입니다. 괄호·따옴표·번호·이모지·영어를 쓰지 말고, 숫자는 한글로 쓰세요.
- 명언·유명인 인용·통계를 쓰지 마세요(출처 확인 불가). 전부 당신의 말로.
- '포기하지 마세요', '당신은 할 수 있어요', '꿈을 향해', '최고의 나' 같은 상투어와 과장된 감탄, 소리치는 말투를 피하세요.
- 훈계 대신 옆에서 말 걸듯이. '여러분' 대신 '당신' 또는 '우리'.
- 문장은 짧게, 모든 문장은 마침표·물음표로 끝내세요(쉼이 거기서 생깁니다).

주제: {theme}"""


def make_script(theme: str, day: str, out: Path) -> dict:
    g = bw.gemini_json(bw.env()["GEMINI_API_KEY"], PROMPT.format(theme=theme))
    script = {"date": day, "kind": "motiv", "theme": theme, "title": g["title"].strip(), "parts": [
        {"id": "line", "text": bw.clean_speech(g["line"])},
        {"id": "body", "text": bw.clean_speech(g["body"])},
        {"id": "close", "text": bw.clean_speech(g["close"])}]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    bw.log(f"원고 {sum(len(p['text']) for p in script['parts'])}자 · {script['title']}")
    return script


def mix(script: dict, out: Path) -> Path:
    """세 부분을 이어 SPEED 로 늘리고 음량을 맞춘다(simbang.join 과 같은 처리). 부분 사이 쉼은 0.6초."""
    inputs, filters = [], []
    n = len(script["parts"])
    for i, p in enumerate(script["parts"]):
        f = Path(p["audio"])
        body = bw.dur(f) / SPEED
        gain = max(-20.0, min(20.0, -15.0 - bw.loudness(f)))
        pad = TAIL if i == n - 1 else 0.6
        inputs += ["-i", str(f)]
        filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,adeclick,atempo={SPEED},"
                       f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=disabled,"
                       f"afade=t=in:d=0.02,afade=t=out:st={max(0.0, body - 0.02):.3f}:d=0.02,"
                       f"apad=pad_dur={pad}[a{i}]")
        p["gap"] = pad
    dst = out / "motiv.m4a"
    chain = "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,adelay={int(HEAD * 1000)}:all=1[out]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters + [chain]),
                    "-map", "[out]", "-c:a", "aac", "-b:a", "160k", str(dst)], check=True)
    return dst


def backdrop() -> Image.Image:
    """어두운 남색→먹색 세로 그라데이션 + 가장자리 어둡게(사진 없이 글이 잘 읽히게)."""
    im = Image.new("RGB", (VW, VH))
    d = ImageDraw.Draw(im)
    for y in range(VH):
        t = y / VH
        d.line([(0, y), (VW, y)], fill=(int(28 - 10 * t), int(34 - 12 * t), int(52 - 22 * t)))
    glow = Image.new("L", (VW, VH), 0)
    ImageDraw.Draw(glow).ellipse((-200, 420, VW + 200, 1500), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return Image.composite(Image.new("RGB", (VW, VH), (70, 62, 54)), im, glow)


def card(text: str, big: bool) -> Image.Image:
    im = backdrop()
    d = ImageDraw.Draw(im)
    fh = sl.font("Pretendard-Bold", 34)
    d.text(((VW - fh.getlength(CHANNEL)) // 2, 210), CHANNEL, font=fh, fill=GOLD)
    size = 84 if big else 64
    f = sl.font("GowunBatang-Bold" if big else "Pretendard-Bold", size)
    lines = sl.wrap(text, f, VW - 160)
    while len(lines) > 5 and size > 44:
        size -= 4
        f = sl.font("GowunBatang-Bold" if big else "Pretendard-Bold", size)
        lines = sl.wrap(text, f, VW - 160)
    lh = int(size * 1.55)
    y = (VH - lh * len(lines)) // 2 - 40
    for ln in lines:
        d.text(((VW - f.getlength(ln)) // 2, y), ln, font=f, fill=GOLD if big else WHITE)
        y += lh
    fa = sl.font("Pretendard-Regular", 24)
    d.text(((VW - fa.getlength(AI_NOTE)) // 2, VH - 150), AI_NOTE, font=fa, fill=DIM)
    return im


def render(script: dict, audio: Path, out: Path) -> Path:
    """묶음(chunk_secs)마다 화면 한 장 — 하루 한 줄은 크게, 나머지는 문장 자막. 끝은 하루 한 줄을 다시 띄운다."""
    fr = out / "frames"
    fr.mkdir(exist_ok=True)
    for old in fr.glob("*.png"):
        old.unlink()
    seq: list[tuple[Path, float]] = []

    def add(img: Image.Image, sec: float) -> None:
        path = fr / f"{len(seq):04d}.png"
        img.save(path)
        seq.append((path, sec))

    line = script["parts"][0]["text"]
    add(card(line, True), HEAD)
    for p in script["parts"]:
        cks = bw.chunks(p["text"], "ko")
        secs = p["qc"]["chunk_secs"]
        if len(secs) != len(cks):                  # 묶음 수가 다르면 글자 수 비례로
            total = sum(secs)
            secs = [total * len(c) / sum(len(x) for x in cks) for c in cks]
        for i, (c, s) in enumerate(zip(cks, secs)):
            extra = p["gap"] if i == len(cks) - 1 else 0.0
            add(card(c, p["id"] == "line"), s / SPEED + extra)
    last, sec = seq[-1]
    seq[-1] = (last, sec - TAIL + 0.3)
    add(card(line, True), TAIL - 0.3)
    lst = out / "frames.txt"
    with lst.open("w", encoding="utf-8") as f:
        for path, sec in seq:
            f.write(f"file '{path.resolve().as_posix()}'\nduration {max(0.05, sec):.3f}\n")
        f.write(f"file '{seq[-1][0].resolve().as_posix()}'\n")
    dst = out / "motiv.mp4"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-i", str(audio), "-map", "0:v", "-map", "1:a", "-vf", f"fps={FPS},format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-g", str(FPS * 2),
                    "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(dst)], check=True)
    return dst


def make_one(v, script: dict, out: Path) -> Path:
    for p in script["parts"]:
        dst = out / f"{p['id']}.wav"
        p["audio"], p["qc"] = str(dst), v.part(p["text"], dst)
        bw.log(f"{p['id']}: {p['qc']['sec']:.0f}초 · 최대 오류 {p['qc']['max_err']:.0%}")
    audio = mix(script, out)
    dst = render(script, audio, out)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst


def worship_busy() -> bool:
    r = subprocess.run(["pgrep", "-f", "build_worship.py|simbang.py"], capture_output=True)
    return r.returncode == 0


def run_bank(bank: Path, until: str | None, limit: int) -> int:
    """은행(jsonl)의 안 만든 원고를 차례로 — 결과는 OUTBOX/motiv/<id>/ (mp4·script.json), 만든 id 는 done.txt.
    GPU 메모리가 크면 restart_if_heavy 가 같은 명령으로 다시 띄우고, done.txt·_chunks 로 이어 간다."""
    done_f = OUT / "done.txt"
    done = set(done_f.read_text(encoding="utf-8").split()) if done_f.exists() else set()
    files = sorted(bank.glob("*.jsonl")) if bank.is_dir() else [bank]
    todo = [m for f in files for m in map(json.loads, filter(str.strip, f.read_text(encoding="utf-8-sig").splitlines()))
            if m["id"] not in done]
    stop = None
    if until:
        now = dt.datetime.now()
        stop = now.replace(hour=int(until[:2]), minute=int(until[3:5]), second=0, microsecond=0)
        if stop <= now:
            stop += dt.timedelta(days=1)
    bw.log(f"은행 {len(todo)}편 남음" + (f" · {stop:%H:%M} 까지" if stop else ""))
    v, made, fails = None, 0, 0
    for m in todo:
        if stop and dt.datetime.now() >= stop or limit and made >= limit:
            break
        while worship_busy():                      # 예배 목소리가 우선 — GPU 를 나눠 쓰지 않는다
            bw.log("예배 작업 중 — 1분 뒤 다시 확인")
            time.sleep(60)
        v = v or bw.Voice("ko")
        out = OUT / m["id"]
        script = {"date": dt.date.today().isoformat(), "kind": "motiv", "id": m["id"], "theme": m["theme"],
                  "title": m["title"], "parts": [{"id": k, "text": m[k]} for k in ("line", "body", "close")]}
        out.mkdir(parents=True, exist_ok=True)
        try:
            t0 = time.time()
            dst = make_one(v, script, out)
            box = out / "box"                       # 다 채운 뒤 한 번에 옮긴다 — 이관이 반쪽 묶음을 집어 가지 않게
            box.mkdir(exist_ok=True)
            sec = bw.dur(dst)
            shutil.move(str(dst), box / f"{m['id']}.mp4")   # 맥에 사본을 남기지 않는다(10-25 사용자: 용량 부족)
            (out / "motiv.m4a").unlink(missing_ok=True)
            (box / "script.json").write_text(json.dumps(
                {k: m[k] for k in ("id", "theme", "title", "line", "body", "close")}
                | {"sec": round(sec, 1), "max_err": max(p["qc"]["max_err"] for p in script["parts"])},
                ensure_ascii=False, indent=1), encoding="utf-8")
            stamp = time.time()                     # 두 파일 시각을 같게 — 이관(5분 지난 파일만)이 둘을 같은 묶음으로 옮기게
            for f in box.iterdir():
                os.utime(f, (stamp, stamp))
            OUTBOX.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(OUTBOX / m["id"], ignore_errors=True)
            box.rename(OUTBOX / m["id"])
            for junk in ("frames", "_chunks"):
                shutil.rmtree(out / junk, ignore_errors=True)
            for w in out.glob("*.wav"):
                w.unlink()
            with done_f.open("a", encoding="utf-8") as f:
                f.write(m["id"] + "\n")
            made, fails = made + 1, 0
            bw.log(f"[{made}] {m['id']} 완성 {sec:.0f}초 · {time.time() - t0:.0f}초 걸림 · {m['title']}")
        except Exception as e:  # noqa: BLE001 — 한 편 실패는 건너뛰고 이어 간다
            fails += 1
            bw.log(f"[실패] {m['id']} {type(e).__name__}: {e}")
            if fails >= 3:
                bw.log("연달아 3번 실패 — 멈춤")
                return 1
    bw.log(f"끝 — 이번에 {made}편")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="일이 손에 안 잡히는 월요일 아침")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--run", help="이어 만들 결과 폴더 이름(없으면 새 번호)")
    ap.add_argument("--bank", help="원고 은행 폴더 또는 jsonl — 안 만든 원고를 차례로 만든다")
    ap.add_argument("--until", help="이 시각(HH:MM)이 지나면 새 편을 시작하지 않는다")
    ap.add_argument("--max", type=int, default=0, help="이번에 만들 최대 편수(0=제한 없음)")
    a = ap.parse_args()
    if a.bank:
        return run_bank(Path(a.bank).expanduser(), a.until, a.max)
    if a.run:
        out = OUT / a.run
    else:
        n = 1
        while (OUT / f"{a.date}_{n:02d}").exists():
            n += 1
        out = OUT / f"{a.date}_{n:02d}"
    sp = out / "script.json"
    script = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else make_script(a.theme, a.date, out)
    dst = make_one(bw.Voice("ko"), script, out)
    bw.log(f"완성 {dst} · {bw.dur(dst):.1f}초 · {script['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

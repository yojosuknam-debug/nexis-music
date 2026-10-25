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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

W = Path(os.environ.get("WORSHIP_DIR", Path(__file__).resolve().parent))   # 맥미니는 레포 밖에 두고 레포의 worship 폴더를 가리킨다
sys.path.insert(0, str(W))
import build_worship as bw  # noqa: E402
import slides as sl  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

OUT = Path(os.environ.get("MOTIV_OUT", Path.home() / "Work" / "nexis-motiv" / "output"))
OUTBOX = Path(os.environ.get("MOTIV_OUTBOX", Path.home() / "Work" / "outbox" / "motiv"))   # archive-outbox 가 미니PC 로 옮긴다
SPEED = float(os.environ.get("MOTIV_SPEED", "0.95"))   # 예배(0.92)보다 조금 힘 있게
BG_DIR = Path(os.environ.get("MOTIV_BG_DIR", Path.home() / "Work" / "nexis-motiv" / "bg"))   # 주제별 배경 묶음(없으면 단색 바탕)
RESTART_EVERY =int(os.environ.get("MOTIV_RESTART_EVERY", "8"))   # 이만큼 만들 때마다 프로세스를 새로 띄운다(0=안 함)
HEAD, TAIL = 0.5, 1.5       # 앞뒤 여백(초) — 끝은 맺는 문장을 잠시 띄워 둔다
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


def scrim(y0: int, y1: int, peak: int) -> Image.Image:
    """글 뒤에 깔 세로 그늘(위아래로 옅어짐) — 그림 배경 위에서도 글이 읽히게."""
    a = Image.new("L", (1, VH), 0)
    mid, half = (y0 + y1) / 2, max(1.0, (y1 - y0) / 2)
    for y in range(VH):
        t = abs(y - mid) / half
        a.putpixel((0, y), int(peak * max(0.0, 1 - t * t)))
    return a.resize((VW, VH))


def card(text: str, big: bool, clear: bool = False) -> Image.Image:
    """clear=True 면 투명 바탕(배경 그림·영상 위에 얹는 글 판) — 글 뒤 그늘과 그림자를 넣는다."""
    im = Image.new("RGBA", (VW, VH), (0, 0, 0, 0)) if clear else backdrop()
    d = ImageDraw.Draw(im)
    size = 84 if big else 64
    f = sl.font("GowunBatang-Bold" if big else "Pretendard-Bold", size)
    lines = sl.wrap(text, f, VW - 160)
    while len(lines) > 5 and size > 44:
        size -= 4
        f = sl.font("GowunBatang-Bold" if big else "Pretendard-Bold", size)
        lines = sl.wrap(text, f, VW - 160)
    lh = int(size * 1.55)
    y = (VH - lh * len(lines)) // 2 - 40
    fh, fa = sl.font("Pretendard-Bold", 34), sl.font("Pretendard-Regular", 24)
    if clear:
        shade = Image.new("RGBA", (VW, VH), (8, 10, 18, 0))
        alpha = scrim(y - 260, y + lh * len(lines) + 220, 175)
        edge = Image.new("L", (1, VH), 0)          # 위·아래 가장자리로 갈수록 어둡게(채널 이름·AI 안내 뒤) — 띠가 지지 않게
        for yy in range(VH):
            edge.putpixel((0, yy), int(150 * max(0.0, 1 - yy / 460, 1 - (VH - yy) / 460)))
        top = bottom = edge.resize((VW, VH))
        shade.putalpha(ImageChops.lighter(ImageChops.lighter(alpha, top), bottom))
        im = Image.alpha_composite(im, shade)
        d = ImageDraw.Draw(im)

    def put(xy, s, font, fill):
        if clear:                                  # 옅은 그림자 — 밝은 그림 위에서도 글 테두리가 보이게
            d.text((xy[0] + 3, xy[1] + 3), s, font=font, fill=(0, 0, 0, 150))
        d.text(xy, s, font=font, fill=fill)

    put(((VW - fh.getlength(CHANNEL)) // 2, 210), CHANNEL, fh, GOLD)
    for ln in lines:
        put(((VW - f.getlength(ln)) // 2, y), ln, f, GOLD if big else WHITE)
        y += lh
    put(((VW - fa.getlength(AI_NOTE)) // 2, VH - 150), AI_NOTE, fa, (200, 196, 188) if clear else DIM)
    return im


THEME_KEY = {"시작": "start", "지침": "tired", "실패 뒤": "fail", "비교": "compare", "관계": "relation", "습관": "habit",
             "공부와 시험": "study", "돈과 일": "work", "몸과 마음": "mind", "작은 기쁨": "joy"}


def pick_bg(theme: str, mid: str) -> Path | None:
    """주제별 배경 묶음(BG_DIR/<주제키>_<scene|girl>.<mp4|png>)에서 고른다 — 편 번호로 화풍을 번갈아, 움직이는 영상이 있으면 먼저."""
    if not BG_DIR.is_dir():
        return None
    key = THEME_KEY.get(theme, "")
    styles = ["scene", "girl"] if int(re.sub(r"\D", "", mid) or 0) % 2 else ["girl", "scene"]
    for st in styles:
        for ext in ("mp4", "png"):
            p = BG_DIR / f"{key}_{st}.{ext}"
            if p.exists():
                return p
    return None


def bg_filter(bg: Path, mid: str, sec: float) -> list[str]:
    """배경 입력 + 필터. 그림은 천천히 확대하며 흐르고(방향은 편마다 다르게), 영상은 끝없이 되풀이한다."""
    if bg.suffix == ".mp4":
        return ["-stream_loop", "-1", "-i", str(bg)], \
            f"[0:v]scale={VW}:{VH}:force_original_aspect_ratio=increase,crop={VW}:{VH},fps={FPS},setsar=1"
    n = int(re.sub(r"\D", "", mid) or 0)
    fx, fy = [(0.5, 0.35), (0.2, 0.5), (0.8, 0.5), (0.5, 0.65)][n % 4]
    frames = int(sec * FPS) + FPS
    z = f"min(1+0.10*on/{frames},1.10)"
    return ["-loop", "1", "-framerate", str(FPS), "-i", str(bg)], (
        f"[0:v]scale={VW * 2}:{VH * 2}:force_original_aspect_ratio=increase,crop={VW * 2}:{VH * 2},"
        f"zoompan=z='{z}':x='(iw-iw/zoom)*{fx}':y='(ih-ih/zoom)*{fy}':d=1:s={VW}x{VH}:fps={FPS},setsar=1")


def render(script: dict, audio: Path, out: Path, bg: Path | None = None, name: str = "motiv.mp4") -> Path:
    """묶음(chunk_secs)마다 화면 한 장 — 하루 한 줄은 크게, 나머지는 문장 자막. 끝은 하루 한 줄을 다시 띄운다.
    bg 가 있으면 글 판을 투명하게 만들어 배경 그림(천천히 확대)·영상(되풀이) 위에 얹는다."""
    clear = bg is not None
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
    add(card(line, True, clear), HEAD)
    for p in script["parts"]:
        cks = bw.chunks(p["text"], "ko")
        secs = p["qc"]["chunk_secs"]
        if len(secs) != len(cks):                  # 묶음 수가 다르면 글자 수 비례로
            total = sum(secs)
            secs = [total * len(c) / sum(len(x) for x in cks) for c in cks]
        for i, (c, s) in enumerate(zip(cks, secs)):
            extra = p["gap"] if i == len(cks) - 1 else 0.0
            add(card(c, p["id"] == "line", clear), s / SPEED + extra)
    last, sec = seq[-1]
    seq[-1] = (last, sec - TAIL + 0.3)
    add(card(line, True, clear), TAIL - 0.3)
    lst = out / "frames.txt"
    with lst.open("w", encoding="utf-8") as f:
        for path, sec in seq:
            f.write(f"file '{path.resolve().as_posix()}'\nduration {max(0.05, sec):.3f}\n")
        f.write(f"file '{seq[-1][0].resolve().as_posix()}'\n")
    dst = out / name
    if not clear:
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-i", str(audio), "-map", "0:v", "-map", "1:a", "-vf", f"fps={FPS},format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-g", str(FPS * 2),
                        "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(dst)], check=True)
        return dst
    sec = bw.dur(audio)
    bin_, bf = bg_filter(bg, script.get("id", "m0"), sec)
    fc = f"{bf},eq=brightness=-0.04:saturation=0.92[bg];[1:v]fps={FPS},format=rgba[ov];" \
         f"[bg][ov]overlay=0:0:format=auto,format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *bin_,
                    "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(audio), "-filter_complex", fc,
                    "-map", "[v]", "-map", "2:a", "-t", f"{sec:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "21", "-g", str(FPS * 2), "-c:a", "copy", "-movflags", "+faststart", str(dst)], check=True)
    return dst


def make_one(v, script: dict, out: Path, bg: Path | None = None) -> Path:
    for p in script["parts"]:
        dst = out / f"{p['id']}.wav"
        p["audio"], p["qc"] = str(dst), v.part(p["text"], dst)
        bw.log(f"{p['id']}: {p['qc']['sec']:.0f}초 · 최대 오류 {p['qc']['max_err']:.0%}")
    audio = mix(script, out)
    dst = render(script, audio, out, bg)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst


def worship_busy() -> bool:
    r = subprocess.run(["pgrep", "-f", "build_worship.py|simbang.py"], capture_output=True)
    return r.returncode == 0


def run_bank(bank: Path, until: str | None, limit: int, redo: set[str] | None = None) -> int:
    """은행(jsonl)의 안 만든 원고를 차례로 — 결과는 OUTBOX/motiv/<id>/ (mp4·script.json), 만든 id 는 done.txt.
    GPU 메모리가 크면 restart_if_heavy 가, RESTART_EVERY 편마다는 여기서 같은 명령으로 다시 띄우고 done.txt·_chunks 로 이어 간다.
    redo: 이 id 들만 다른 씨앗으로 다시 만든다(기록은 redone.txt)."""
    done_f = OUT / ("redone.txt" if redo else "done.txt")
    done = set(done_f.read_text(encoding="utf-8").split()) if done_f.exists() else set()
    files = sorted(bank.glob("*.jsonl")) if bank.is_dir() else [bank]
    todo = [m for f in files for m in map(json.loads, filter(str.strip, f.read_text(encoding="utf-8-sig").splitlines()))
            if m["id"] not in done and (redo is None or m["id"] in redo)]
    if redo:                                       # 같은 씨앗이면 같은 소리가 나온다 — 씨앗을 옮기고 시도 횟수를 늘린다
        import torch
        seed = torch.manual_seed
        torch.manual_seed = lambda s: seed(s + 500)
        bw.TRIES = 5
    stop = None
    if until:
        now = dt.datetime.now()
        stop = now.replace(hour=int(until[:2]), minute=int(until[3:5]), second=0, microsecond=0)
        if stop <= now:
            stop += dt.timedelta(days=1)
    bw.log(f"은행 {len(todo)}편 남음" + (f" · {stop:%H:%M} 까지" if stop else ""))
    v, made, fails = None, int(os.environ.get("MOTIV_MADE", "0")), 0
    for i, m in enumerate(todo):
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
            bg = pick_bg(m["theme"], m["id"])
            dst = make_one(v, script, out, bg)
            if bg:
                script["bg"] = bg.name
            box = out / "box"                       # 다 채운 뒤 한 번에 옮긴다 — 이관이 반쪽 묶음을 집어 가지 않게
            box.mkdir(exist_ok=True)
            sec = bw.dur(dst)
            shutil.move(str(dst), box / f"{m['id']}.mp4")   # 맥에 사본을 남기지 않는다(10-25 사용자: 용량 부족)
            (out / "motiv.m4a").unlink(missing_ok=True)
            (box / "script.json").write_text(json.dumps(
                {k: m[k] for k in ("id", "theme", "title", "line", "body", "close")}
                | {"sec": round(sec, 1), "max_err": max(p["qc"]["max_err"] for p in script["parts"])}
                | ({"redo": True} if redo else {}) | ({"bg": script["bg"]} if "bg" in script else {}),
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
            bw.log(f"[{made}] {m['id']} 완성 {sec:.0f}초 · {time.time() - t0:.0f}초 걸림 · 최대 오류 "
                   f"{max(p['qc']['max_err'] for p in script['parts']):.0%} · {m['title']}")
            if RESTART_EVERY and made % RESTART_EVERY == 0 and i + 1 < len(todo):
                # 한 프로세스로 오래 돌리면 편당 86초 → 404초로 점점 느려졌다(10-25 밤샘) — 몇 편마다 새로 띄운다
                bw.log(f"  {RESTART_EVERY}편마다 새로 띄움(지금까지 {made}편)")
                os.environ["MOTIV_MADE"] = str(made)
                sys.stdout.flush()
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:  # noqa: BLE001 — 한 편 실패는 건너뛰고 이어 간다
            fails += 1
            bw.log(f"[실패] {m['id']} {type(e).__name__}: {e}")
            if fails >= 3:
                bw.log("연달아 3번 실패 — 멈춤")
                return 1
    bw.log(f"끝 — 이번에 {made}편")
    return 0


def compare(bank: Path, mid: str, bgs: list[str]) -> int:
    """같은 원고·같은 목소리로 배경만 바꾼 영상 여러 개 — OUT/compare-<id>/<배경 이름>.mp4."""
    files = sorted(bank.glob("*.jsonl")) if bank.is_dir() else [bank]
    m = next(x for f in files for x in map(json.loads, filter(str.strip, f.read_text(encoding="utf-8-sig").splitlines()))
             if x["id"] == mid)
    out = OUT / f"compare-{mid}"
    out.mkdir(parents=True, exist_ok=True)
    script = {"date": dt.date.today().isoformat(), "kind": "motiv", "id": mid, "theme": m["theme"], "title": m["title"],
              "parts": [{"id": k, "text": m[k]} for k in ("line", "body", "close")]}
    v = bw.Voice("ko")
    for p in script["parts"]:
        dst = out / f"{p['id']}.wav"
        p["audio"], p["qc"] = str(dst), v.part(p["text"], dst)
    audio = mix(script, out)
    for b in bgs:
        bg = None if b == "none" else BG_DIR / b
        name = ("plain" if bg is None else bg.stem + ("_loop" if bg.suffix == ".mp4" else "_still")) + ".mp4"
        t0 = time.time()
        dst = render(script, audio, out, bg, name)
        bw.log(f"비교본 {dst.name} · {bw.dur(dst):.1f}초 · 화면 만들기 {time.time() - t0:.0f}초")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="일이 손에 안 잡히는 월요일 아침")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--run", help="이어 만들 결과 폴더 이름(없으면 새 번호)")
    ap.add_argument("--bank", help="원고 은행 폴더 또는 jsonl — 안 만든 원고를 차례로 만든다")
    ap.add_argument("--until", help="이 시각(HH:MM)이 지나면 새 편을 시작하지 않는다")
    ap.add_argument("--max", type=int, default=0, help="이번에 만들 최대 편수(0=제한 없음)")
    ap.add_argument("--redo", help="다시 만들 id(쉼표로 구분) — 은행에서 이 편들만 다른 씨앗으로")
    ap.add_argument("--compare", help="비교본: 은행의 이 id 한 편을 목소리는 한 번만 만들고 --bgs 배경마다 영상으로")
    ap.add_argument("--bgs", default="none", help="비교할 배경 파일들(쉼표, BG_DIR 기준 이름). none = 단색 바탕")
    a = ap.parse_args()
    if a.compare:
        return compare(Path(a.bank or "bank").expanduser(), a.compare, a.bgs.split(","))
    if a.bank:
        redo = set(a.redo.split(",")) if a.redo else None
        return run_bank(Path(a.bank).expanduser(), a.until, a.max, redo)
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

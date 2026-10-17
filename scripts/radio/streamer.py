"""
넥시스 뮤직 24시간 방송 송출기.

    python scripts/radio/streamer.py              # 실제 방송 (R2 radio/)
    python scripts/radio/streamer.py --prefix radio-test --minutes 3   # 시험

공개 앨범을 무작위로 골라 1번 곡부터 끝까지 틀고 다음 앨범으로 넘어간다.
소리는 HLS(10초 조각)로 만들어 R2 에 올린다 — 청취자는 미니PC 가 아니라 R2 에서 받는다.
미니PC 는 밖으로 올리기만 하므로 터널·포트·DNS 를 건드리지 않는다.

    https://audio.yojosuknam.com/radio/live.m3u8        방송 주소
    https://audio.yojosuknam.com/radio/nowplaying.json  지금·다음·최근 곡

곡 목록 = 사이트의 /album/radio.json (build_pages.py 가 만든다).
사이트에 공개된 앨범만 나오고, .nojukebox 로 숨기면 다음 목록 갱신 때 방송에서도 빠진다.
음원은 이 기계의 앨범 원본을 우선 읽고, 없으면 R2 주소에서 읽는다.

환경변수:
    RADIO_LIST_URL   곡 목록 주소 (기본 https://music.yojosuknam.com/album/radio.json)
    RADIO_BITRATE    기본 128k
    RADIO_CHANNEL    채널 이름 일부 — 지정하면 그 채널 앨범만 (장르별 방송용)
    RADIO_ICECAST_PASSWORD  있으면 같은 소리를 MP3 직통으로도 Icecast 에 보낸다(라디오 가든·TuneIn 용)
    RADIO_ICECAST_HOST      기본 icecast:8000,  RADIO_ICECAST_MOUNT 기본 /live.mp3
    JUKEBOX_INPUT_DIR / JUKEBOX_ENV_FILE  → ../jukebox/_env.py 참고
자격증명 값은 메모리에만 두고 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import queue
import random
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jukebox"))
import _env  # noqa: E402

import boto3  # noqa: E402
from botocore.config import Config  # noqa: E402

LIST_URL = os.environ.get("RADIO_LIST_URL", "https://music.yojosuknam.com/album/radio.json")
BITRATE = os.environ.get("RADIO_BITRATE", "128k")
CHANNEL = os.environ.get("RADIO_CHANNEL", "").strip()
UA = "Mozilla/5.0 (X11; Linux x86_64) NexisRadio/1.0"

RATE, CH = 44100, 2
BPS = RATE * CH * 2                 # s16le 1초 바이트
SEG = 10                            # HLS 조각 길이(초)
LIST_SIZE = 6                       # 재생목록에 남길 조각 수 = 60초
LEAD = 2.0                          # 실제 시각보다 앞서 밀어 넣는 여유(초)
ALBUM_GAP = 2.0                     # 앨범 사이 무음(초)
LIST_REFRESH = 30 * 60              # 곡 목록 다시 받기(초)
STALL_LIMIT = 90                    # 재생목록이 이만큼 안 바뀌면 멈춘 것으로 보고 종료(재시작은 docker)

stop = threading.Event()


def log(msg: str) -> None:
    print(time.strftime("%m-%d %H:%M:%S"), msg, flush=True)


# ── 곡 목록 ───────────────────────────────────────────────────────────────
_list_cache: tuple[float, list[dict]] = (0.0, [])


def albums() -> list[dict]:
    """공개 앨범 목록. 받기에 실패하면 직전 목록으로 계속 간다."""
    global _list_cache
    at, cached = _list_cache
    if cached and time.time() - at < LIST_REFRESH:
        return cached
    try:
        req = urllib.request.Request(LIST_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        got = [a for a in data["albums"] if a.get("tracks")]
        if CHANNEL:
            got = [a for a in got if CHANNEL.lower() in a.get("channel", "").lower()]
        if got:
            _list_cache = (time.time(), got)
            log(f"곡 목록 {len(got)}앨범 · {sum(len(a['tracks']) for a in got)}곡")
            return got
    except Exception as e:  # noqa: BLE001
        log(f"[경고] 곡 목록 받기 실패({type(e).__name__}) — 직전 목록 사용")
    if not cached:
        raise RuntimeError("곡 목록이 비어 있습니다")
    _list_cache = (time.time() - LIST_REFRESH + 300, cached)   # 5분 뒤 재시도
    return cached


def source_of(album: dict, track: dict) -> str:
    """앨범 원본이 이 기계에 있으면 그 파일, 없으면 R2 주소."""
    folder, name = album.get("folder"), track.get("file")
    if folder and name:
        p = _env.input_dir() / folder / "tracks" / name
        if p.exists():
            return str(p)
    return track["url"]


class Picker:
    """앨범을 무작위로 고르되 최근에 나온 앨범은 피한다."""

    def __init__(self) -> None:
        self.recent: deque[str] = deque()

    def next(self) -> dict:
        pool = albums()
        keep = max(1, min(len(pool) // 2, 40))
        while len(self.recent) > keep:
            self.recent.popleft()
        fresh = [a for a in pool if a["slug"] not in self.recent] or pool
        a = random.choice(fresh)
        self.recent.append(a["slug"])
        return a


# ── R2 ────────────────────────────────────────────────────────────────────
def r2():
    v = _env.load_secrets()
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{v['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=v["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=v["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 4, "mode": "standard"},
                      connect_timeout=10, read_timeout=30, max_pool_connections=4),
    )
    return s3, v["R2_BUCKET"], v["R2_PUBLIC_BASE"].rstrip("/")


def put(s3, bucket: str, key: str, body: bytes, ctype: str, cache: str) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=ctype, CacheControl=cache)


class Uploader(threading.Thread):
    """ffmpeg 가 만든 조각을 R2 로 올리고, 재생목록에서 빠진 조각은 지운다."""

    def __init__(self, s3, bucket: str, prefix: str, outdir: Path) -> None:
        super().__init__(daemon=True)
        self.s3, self.bucket, self.prefix, self.out = s3, bucket, prefix, outdir
        self.sent: dict[str, float] = {}       # 올린 조각 → 재생목록에서 빠진 시각(0=아직 목록에 있음)
        self.last_change = time.time()
        self.uploaded_segments = 0

    def run(self) -> None:
        last = ""
        while not stop.is_set():
            try:
                m3u8 = self.out / "live.m3u8"
                text = m3u8.read_text(encoding="utf-8") if m3u8.exists() else ""
                if text and text != last:
                    segs = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
                    for s in segs:
                        if s not in self.sent:
                            put(self.s3, self.bucket, f"{self.prefix}/{s}", (self.out / s).read_bytes(),
                                "video/mp2t", "public, max-age=86400, immutable")
                            self.sent[s] = 0.0
                            self.uploaded_segments += 1
                    put(self.s3, self.bucket, f"{self.prefix}/live.m3u8", text.encode("utf-8"),
                        "application/vnd.apple.mpegurl", "no-cache, max-age=0")
                    last, self.last_change = text, time.time()
                    now = time.time()
                    for s in list(self.sent):
                        if s not in segs and not self.sent[s]:
                            self.sent[s] = now
                        elif self.sent[s] and now - self.sent[s] > 120:   # 늦게 온 청취자 몫으로 2분 더 둔다
                            self.s3.delete_object(Bucket=self.bucket, Key=f"{self.prefix}/{s}")
                            del self.sent[s]
            except FileNotFoundError:
                pass                       # ffmpeg 가 조각을 지우는 순간과 겹침 — 다음 바퀴에 다시
            except Exception as e:  # noqa: BLE001
                log(f"[경고] 업로드 실패({type(e).__name__}) — 다음 바퀴에 재시도")
            stop.wait(1.0)


def clean_old_segments(s3, bucket: str, prefix: str) -> None:
    """지난 실행이 남긴 조각 정리(시작할 때 한 번)."""
    n = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=f"{prefix}/s"):
        keys = [{"Key": o["Key"]} for o in page.get("Contents", []) if o["Key"].endswith(".ts")]
        for i in range(0, len(keys), 1000):
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys[i:i + 1000], "Quiet": True})
            n += len(keys[i:i + 1000])
    if n:
        log(f"지난 조각 {n}개 정리")


# ── 지금 나오는 곡 ─────────────────────────────────────────────────────────
class NowPlaying:
    """nowplaying.json — 곡이 바뀔 때마다 올린다.
    at = 그 곡이 방송 시각으로 시작하는 때(밀리초). 청취자는 HLS 지연(약 30초)만큼 늦게 듣는다.
    HLS 조각에 EXT-X-PROGRAM-DATE-TIME 이 있어 플레이어가 정확히 맞출 수 있다."""

    def __init__(self, s3, bucket: str, prefix: str) -> None:
        self.s3, self.bucket, self.prefix = s3, bucket, prefix
        self.history: deque[dict] = deque(maxlen=10)

    def publish(self, album: dict, idx: int, at: float) -> None:
        def item(t: dict, start: float) -> dict:
            return {"at": int(start * 1000), "ms": t["ms"], "n": t["n"], "title": t["title"],
                    "youtube": t.get("youtube", ""), "album": album["title"],
                    "channel": album.get("channel", ""), "cover": album["cover"], "page": album["page"],
                    "video": album.get("video", "")}

        tracks = album["tracks"]
        cur = item(tracks[idx], at)
        if not self.history or self.history[-1]["at"] != cur["at"]:
            self.history.append(cur)
        nxt, t0 = [], at + tracks[idx]["ms"] / 1000
        for t in tracks[idx + 1: idx + 4]:
            nxt.append(item(t, t0))
            t0 += t["ms"] / 1000
        body = {"updated": int(time.time() * 1000), "delay_hint_s": SEG * 3,
                "now": cur, "next": nxt, "recent": list(self.history)[:-1][::-1]}
        try:
            put(self.s3, self.bucket, f"{self.prefix}/nowplaying.json",
                json.dumps(body, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", "no-cache, max-age=0")
        except Exception as e:  # noqa: BLE001
            log(f"[경고] nowplaying 올리기 실패({type(e).__name__})")


# ── 소리 ──────────────────────────────────────────────────────────────────
def encoder(outdir: Path) -> subprocess.Popen:
    start_no = int(time.time() // SEG)        # 재시작해도 조각 번호가 뒤로 가지 않게
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostats",
           "-f", "s16le", "-ar", str(RATE), "-ac", str(CH), "-i", "pipe:0",
           "-c:a", "aac", "-b:a", BITRATE,
           "-f", "hls", "-hls_time", str(SEG), "-hls_list_size", str(LIST_SIZE),
           "-hls_flags", "delete_segments+program_date_time+independent_segments+omit_endlist+temp_file",
           "-start_number", str(start_no),
           "-hls_segment_filename", str(outdir / "s%d.ts"), str(outdir / "live.m3u8")]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def decoder(src: str) -> subprocess.Popen:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error"]
    if src.startswith("http"):
        cmd += ["-user_agent", UA, "-reconnect", "1", "-reconnect_delay_max", "5"]
    cmd += ["-i", src, "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-f", "s16le", "-ar", str(RATE), "-ac", str(CH), "pipe:1"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)


class Mirror(threading.Thread):
    """같은 소리를 MP3 직통으로 Icecast 에 보낸다(라디오 가든·TuneIn·radio.net 은 HLS 를 받지 않는다).
    본방송(HLS)을 절대 막지 않도록 큐로 떼어 놓는다 — 밀리면 버리고, 끊기면 5초 뒤 다시 붙는다.
    비밀번호가 ffmpeg 오류 메시지에 섞여 로그로 새지 않게 가린다."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.pw = os.environ.get("RADIO_ICECAST_PASSWORD", "").strip()
        self.host = os.environ.get("RADIO_ICECAST_HOST", "icecast:8000")
        self.mount = os.environ.get("RADIO_ICECAST_MOUNT", "/live.mp3")
        self.q: queue.Queue[bytes] = queue.Queue(maxsize=40)      # 0.25초 × 40 = 10초
        self.dropped = 0

    @property
    def on(self) -> bool:
        return bool(self.pw)

    def put(self, data: bytes) -> None:
        if not self.on:
            return
        try:
            self.q.put_nowait(data)
        except queue.Full:
            self.dropped += 1

    def _mask(self, line: str) -> str:
        return line.replace(self.pw, "***") if self.pw else line

    def _log_stderr(self, proc: subprocess.Popen) -> None:
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                log("  [직통] " + self._mask(line))

    def run(self) -> None:
        if not self.on:
            return
        url = f"icecast://source:{self.pw}@{self.host}{self.mount}"
        while not stop.is_set():
            proc = subprocess.Popen(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats",
                 "-f", "s16le", "-ar", str(RATE), "-ac", str(CH), "-i", "pipe:0",
                 "-c:a", "libmp3lame", "-b:a", "128k", "-content_type", "audio/mpeg",
                 "-ice_name", "yojosuknam Radio", "-ice_genre", "Various",
                 "-ice_description", "yojosuknam 의 앨범을 24시간 이어서 틉니다",
                 "-ice_url", "https://music.yojosuknam.com/radio", "-f", "mp3", url],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            threading.Thread(target=self._log_stderr, args=(proc,), daemon=True).start()
            log(f"직통 송출 연결 → {self.host}{self.mount}")
            try:
                while not stop.is_set() and proc.poll() is None:
                    try:
                        proc.stdin.write(self.q.get(timeout=1))
                    except queue.Empty:
                        continue
            except (BrokenPipeError, OSError):
                pass
            finally:
                proc.kill()
                proc.wait()
            if not stop.is_set():
                log("[경고] 직통 송출이 끊겼습니다 — 5초 뒤 다시 연결 (본방송은 그대로)")
                with self.q.mutex:
                    self.q.queue.clear()
                stop.wait(5)

    def meta(self, text: str) -> None:
        """라디오 앱에 보이는 '지금 곡' 제목(Icecast metadata) — 실패해도 무시."""
        if not self.on:
            return

        def go() -> None:
            q = urllib.parse.urlencode({"mount": self.mount, "mode": "updinfo", "song": text})
            req = urllib.request.Request(f"http://{self.host}/admin/metadata?{q}")
            req.add_header("Authorization", "Basic " + base64.b64encode(f"source:{self.pw}".encode()).decode())
            try:
                urllib.request.urlopen(req, timeout=5).read()
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=go, daemon=True).start()


class Clock:
    """보낸 소리 길이를 실제 시각에 맞춰 흘려보낸다(LEAD 초만큼만 앞서게)."""

    def __init__(self, mirror: "Mirror | None" = None) -> None:
        self.t0 = time.monotonic()
        self.wall0 = time.time()
        self.sent = 0
        self.mirror = mirror

    def stream_wall(self) -> float:
        """지금 밀어 넣는 소리가 방송 시각으로 언제인가."""
        return self.wall0 + self.sent / BPS

    def feed(self, enc: subprocess.Popen, data: bytes) -> None:
        enc.stdin.write(data)
        if self.mirror:
            self.mirror.put(data)
        self.sent += len(data)
        ahead = self.sent / BPS - (time.monotonic() - self.t0)
        if ahead > LEAD:
            time.sleep(ahead - LEAD)
        elif ahead < -20:          # 크게 밀렸으면(원격 음원 지연 등) 시계를 다시 맞춘다
            shift = -ahead - LEAD
            self.t0 -= shift
            self.wall0 += shift


def play_track(enc, clock: Clock, src: str) -> bool:
    dec = decoder(src)
    chunk = BPS // 4
    got = 0
    try:
        while not stop.is_set():
            data = dec.stdout.read(chunk)
            if not data:
                break
            if len(data) % 4:
                data = data[: len(data) - len(data) % 4]
            clock.feed(enc, data)
            got += len(data)
    finally:
        dec.kill()
        dec.wait()
    return got > BPS            # 1초도 못 읽었으면 실패


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="radio", help="R2 경로(시험은 radio-test)")
    ap.add_argument("--minutes", type=float, default=0, help="이만큼만 돌고 끝낸다(시험용)")
    a = ap.parse_args()
    prefix = a.prefix.strip("/")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())

    s3, bucket, public = r2()
    clean_old_segments(s3, bucket, prefix)
    log(f"방송 주소 {public}/{prefix}/live.m3u8")

    outdir = Path(tempfile.mkdtemp(prefix="nexis-radio-"))
    enc = encoder(outdir)
    up = Uploader(s3, bucket, prefix, outdir)
    up.start()
    now = NowPlaying(s3, bucket, prefix)
    mirror = Mirror()
    mirror.start()
    picker, clock = Picker(), Clock(mirror)
    deadline = time.time() + a.minutes * 60 if a.minutes else 0
    fails = 0

    try:
        while not stop.is_set():
            album = picker.next()
            log(f"▶ 앨범 {album['title']} ({len(album['tracks'])}곡)")
            for i, t in enumerate(album["tracks"]):
                if stop.is_set():
                    break
                now.publish(album, i, clock.stream_wall())
                mirror.meta(f"{t['title']} — {album['title']}")
                src = source_of(album, t)
                log(f"  {t['n']:02d} {t['title']}  [{'원본' if not src.startswith('http') else 'R2'}]")
                if play_track(enc, clock, src):
                    fails = 0
                else:
                    fails += 1
                    log(f"  [경고] 재생 실패 — 건너뜀 ({fails}회 연속)")
                    if fails >= 10:
                        raise RuntimeError("연속 10곡 재생 실패")
                if enc.poll() is not None:
                    raise RuntimeError("인코더가 멈췄습니다")
                if time.time() - up.last_change > STALL_LIMIT:
                    raise RuntimeError("재생목록이 갱신되지 않습니다")
                if deadline and time.time() > deadline:
                    stop.set()
            if not stop.is_set():
                clock.feed(enc, b"\0" * int(BPS * ALBUM_GAP) // 4 * 4)
    except BrokenPipeError:
        log("[에러] 인코더 연결이 끊겼습니다")
        return 1
    except RuntimeError as e:
        log(f"[에러] {e}")
        return 1
    finally:
        stop.set()
        try:
            enc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            enc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            enc.kill()
        log(f"종료 — 조각 {up.uploaded_segments}개 올림"
            + (f" · 직통 밀려서 버린 소리 {mirror.dropped * 0.25:.0f}초" if mirror.dropped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

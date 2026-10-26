"""
동기부여 쇼츠 하루 한 편 올리기(nexis-motiv '하루 한 줄, 동기부여') — 미니PC 에서 실행(10-25 사용자).

    python3 motiv_publish.py [--dry-run] [--id m0001]

- 순서: /mnt/external/nexis-motiv/업로드/순서.txt — 처음 한 번 무작위로 섞어 두고, 새 편은 섞어서 뒤에 붙인다(겹치지 않게).
- 기록: 업로드/올린기록.csv (번호·시각·주소). 이미 올린 편은 다시 올리지 않는다.
- 제목·설명·태그: 업로드/메타/<id>.json (레포 data/motiv/meta.jsonl 에서 나눈 것). 없으면 원고로 기본 문구.
- 실제 업로드는 이미 돌고 있는 autovid-bot 컨테이너의 youtube_upload(nexis-motiv 토큰)로 — 컨테이너는 바꾸지 않는다.
  영상은 컨테이너가 보는 /mnt/external/autovid/output/motiv-upload/ 에 잠깐 복사했다가 지운다.
- 목소리가 AI 합성이라 '변경·합성 콘텐츠'(containsSyntheticMedia)를 켠다.
- 텔레그램 알림(10-26): 업로드 실패·예상 못 한 오류, 남은 편이 LOW 이하로 줄면 '원고 더 쓰기' 알림.
  토큰·chat_id 는 ~/autovid/.env.local 에서만 읽고 화면·로그·명령줄에 싣지 않는다(autovid_cron_guard.sh 와 같은 방식).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import re
import shutil
import subprocess
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("/mnt/external/nexis-motiv")
UP = ROOT / "업로드"
SHARE = Path("/mnt/external/autovid/output/motiv-upload")   # 컨테이너 안 /app/output/motiv-upload
APP = Path.home() / "autovid"
LOW = 7                                                     # 남은 편이 이만큼 이하면 원고 더 쓰라고 알린다

CODE = r"""
import json, sys
from src import youtube_upload as y, channels
from googleapiclient.discovery import build
mid = sys.argv[1]
meta = json.load(open(f"/app/output/motiv-upload/{mid}.json", encoding="utf-8"))
url = y.upload(f"/app/output/motiv-upload/{mid}.mp4", meta, channel="nexis-motiv", privacy="public")
print("RESULT", url, flush=True)   # 올라간 뒤엔 무슨 일이 있어도 기록되게 먼저 찍는다(다음 날 같은 편 중복 방지)
vid = url.rsplit("/", 1)[-1]
try:
    yt = build("youtube", "v3", credentials=y._credentials(channels.cfg("nexis-motiv")))
    yt.videos().update(part="status", body={"id": vid, "status": {"privacyStatus": "public",
        "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}).execute()
    print("SYNTHETIC ok")
except Exception as e:
    print("SYNTHETIC fail", type(e).__name__, str(e)[:200])
"""


def notify(text: str) -> None:
    """텔레그램 — 값은 .env.local 에서만 읽고 POST 본문으로 보낸다(argv·로그 노출 없음). 실패해도 업로드엔 영향 없게."""
    env = {}
    try:
        for ln in (APP / ".env.local").read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    tok, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("[알림] 텔레그램 설정 없음 — 생략")
        return
    data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20).read()
    except Exception as e:                         # 오류 문구에 주소(토큰)가 섞일 수 있어 종류만 남긴다
        print("[알림] 보내기 실패", type(e).__name__)


def default_meta(m: dict) -> dict:
    return {"title": f"{m['title']} #shorts",
            "description": f"{m['line']}\n\n매일 하루 한 줄, 마음을 다잡는 짧은 이야기.\n목소리는 AI로 합성했습니다.\n\n"
                           "#동기부여 #하루한줄 #위로 #자기계발 #shorts",
            "tags": ["동기부여", "하루한줄", "위로", "자기계발", "좋은글", m["theme"]]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", help="이 편을 올린다(순서 무시)")
    a = ap.parse_args()
    (UP / "메타").mkdir(parents=True, exist_ok=True)
    ids = sorted(p.stem for p in (ROOT / "원고").glob("m*.json"))
    order_f, log_f = UP / "순서.txt", UP / "올린기록.csv"
    order = order_f.read_text(encoding="utf-8").split() if order_f.exists() else []
    new = [i for i in ids if i not in order]
    if new:                                        # 새 편은 섞어서 뒤에 — 이미 정한 순서는 그대로
        random.shuffle(new)
        order += new
        order_f.write_text("\n".join(order) + "\n", encoding="utf-8")
    done = set()
    if log_f.exists():
        done = {r["번호"] for r in csv.DictReader(log_f.open(encoding="utf-8-sig"))}
    mid = a.id or next((i for i in order if i not in done), None)
    if not mid:
        print("올릴 편 없음 — 모두 올렸다")
        notify("📭 동기부여 쇼츠: 올릴 편이 없습니다 — 모두 올렸어요.\n새 원고·영상을 만들고 motiv_collect.py 를 돌려 주세요.")
        return 0
    if mid in done:
        print(f"{mid} 은 이미 올렸다")
        return 1
    m = json.loads((ROOT / "원고" / f"{mid}.json").read_text(encoding="utf-8"))
    mp4 = next((ROOT / "영상").glob(f"{mid}_*.mp4"))
    mf = UP / "메타" / f"{mid}.json"
    meta = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else default_meta(m)
    left = len([i for i in order if i not in done]) - 1
    print(f"{dt.datetime.now():%F %T} {mid} · {meta['title']} · 남은 편 {left}")
    if a.dry_run:
        print(json.dumps(meta, ensure_ascii=False, indent=1))
        return 0
    SHARE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mp4, SHARE / f"{mid}.mp4")
    (SHARE / f"{mid}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    try:
        r = subprocess.run(["/usr/bin/docker", "compose", "exec", "-T", "autovid-bot", "python", "-c", CODE, mid],
                           cwd=APP, capture_output=True, text=True, timeout=1800)
    finally:
        for f in (SHARE / f"{mid}.mp4", SHARE / f"{mid}.json"):
            f.unlink(missing_ok=True)
    print(r.stdout[-2000:], r.stderr[-2000:])
    url = (re.search(r"RESULT (\S+)", r.stdout) or [None, None])[1]
    if not url:
        print("업로드 실패")
        why = next((ln for ln in reversed((r.stdout + r.stderr).splitlines()) if re.search(r"Error|Exception|error:", ln)), "")
        notify(f"🚨 동기부여 쇼츠 업로드 실패\n\n편: {mid} · {meta['title']}\n시각: {dt.datetime.now():%F %H:%M}\n"
               f"종료 코드: {r.returncode}\n원인: {why[:200] or '알 수 없음'}\n로그: {UP}/upload.log")
        return 1
    new_file = not log_f.exists()
    with log_f.open("a", encoding="utf-8-sig" if new_file else "utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["번호", "올린 시각", "주소", "제목"])
        w.writerow([mid, f"{dt.datetime.now():%F %T}", url, meta["title"]])
    print(f"업로드 완료 {mid} {url}")
    if left <= LOW:
        notify(f"✍️ 동기부여 쇼츠: 올릴 편이 {left}편 남았습니다(약 {left}일치).\n원고를 더 쓰고 motiv_collect.py 를 돌려 주세요.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:                         # 영상 없음·시간 초과 등 — 조용히 죽지 않게
        traceback.print_exc()
        notify(f"🚨 동기부여 쇼츠 업로드 오류\n\n시각: {dt.datetime.now():%F %H:%M}\n"
               f"오류: {type(e).__name__}: {str(e)[:200]}\n로그: {UP}/upload.log")
        raise SystemExit(1)

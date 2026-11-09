"""유튜브에 공개된 새 앨범을 주크박스에 자동 발행한다 — 미니PC 크론이 매일 부른다.

    python scripts/jukebox/auto_publish.py            새 앨범이 있으면 발행
    python scripts/jukebox/auto_publish.py --check    무엇이 발행될지만 출력

새 앨범이 없는 날은 아무것도 하지 않고 알림도 보내지 않는다.
실제 발행은 텔레그램 /jukebox 와 같은 코드(bot_command._work)가 하고,
push 되면 GitHub Actions(deploy.yml)가 사이트에 배포한다.

유튜브에 아직 없는 앨범은 scan_albums.py 가 JUKEBOX_RELEASED_ONLY 로 걸러 발행되지 않는다.
"""
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts" / "worship"))

import bot_command
import release_gate
from worship_ops import notify

LOCK_FILE = "/tmp/jukebox-auto.lock"
GENERATED = ["scripts/jukebox/catalog.json", "scripts/jukebox/assets"]
# 단계별 진행 메시지는 빼고 시작·실패·완료만 텔레그램으로 보낸다
NOTIFY_PREFIXES = ("❌", "⚠️", "🚀")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=180)


def pipeline_running() -> bool:
    """영상 제작 컨테이너가 돌고 있으면 그 작업이 먼저다(/jukebox 도 이때는 거절된다)."""
    r = subprocess.run(["docker", "ps", "-q", "--filter", "name=suno-pipeline-run"],
                       capture_output=True, text=True, timeout=30)
    return r.returncode != 0 or bool(r.stdout.strip())


def send(text: str) -> None:
    print(text, flush=True)
    if text.startswith(NOTIFY_PREFIXES):
        notify(text)


def main() -> int:
    check_only = "--check" in sys.argv[1:]

    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("이미 실행 중입니다.")
        return 0

    git("checkout", "--", *GENERATED)
    pulled = git("pull", "--ff-only", "-q")
    if pulled.returncode != 0:
        notify("⚠️ 주크박스 자동 발행 중단 — 미니PC 레포를 최신으로 받지 못했습니다.\n"
               + pulled.stderr.strip()[:300])
        return 1

    ready, waiting = release_gate.split_new_albums()
    print(f"발행 대상 {len(ready)}개: {', '.join(ready)}")
    print(f"유튜브 대기 {len(waiting)}개: {', '.join(waiting)}")
    if check_only or not ready:
        return 0

    if pipeline_running():
        print("영상 제작 중이라 다음 실행으로 미룹니다.")
        return 0

    notify(f"🎧 주크박스 자동 발행 시작 — 새 앨범 {len(ready)}개\n" + "\n".join(ready))
    os.environ["JUKEBOX_RELEASED_ONLY"] = "1"
    bot_command._work(send)
    return 0


if __name__ == "__main__":
    sys.exit(main())

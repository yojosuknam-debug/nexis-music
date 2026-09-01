"""
0단계 — 미니PC(원본 정본)에서 새 앨범 가져오기

앨범은 미니PC `/mnt/external/suno-playlist/input` 에 쌓인다. 데스크탑은 사본이므로,
주크박스를 갱신하기 전에 **미니PC에 있고 여기 없는(또는 달라진) 앨범만** 받아온다.

  * 비교 기준: 폴더별 mp3 개수 + 총 바이트. 같으면 건너뛴다.
  * 전송 방식: tar over ssh (폴더 단위, 한 번의 연결로 여러 개)
  * 미니PC 는 읽기만 한다. 아무것도 바꾸지 않는다.

⚠️ git-bash 의 ssh 는 인증 에이전트를 못 타서 멈춘다. 반드시 Windows OpenSSH 를 쓴다.

사용법:
    python scripts/jukebox/sync_from_minipc.py            # 차이만 받아온다
    python scripts/jukebox/sync_from_minipc.py --dry-run  # 무엇을 받을지만 본다
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
HOST = "minipc"
REMOTE = "/mnt/external/suno-playlist/input"
LOCAL = Path(r"d:/YH/APP/youtube-playlist/suno-playlist-video/input")

# 앨범이 아닌 보관 폴더 — 비교에서 제외한다
SKIP = {"완료", "output", "video_library"}


def remote_inventory() -> dict[str, tuple[int, int]]:
    """미니PC 앨범 폴더별 (mp3 개수, 총 바이트)."""
    # 파이프라인이 실제로 읽는 것은 파일명이 트랙번호로 시작하는 mp3 뿐이다(01_*.mp3).
    # 개정 전 잔여 파일까지 세면 영영 "달라짐"으로 잡혀 매번 재전송한다.
    cmd = (f'cd {shlex.quote(REMOTE)} && for d in */; do n="${{d%/}}"; '
           'L=$(find "$d" -type f -iname "*.mp3" -printf "%f|%s\\n" 2>/dev/null | grep "^[0-9]"); '
           'c=$(printf "%s\\n" "$L" | grep -c . ); '
           'b=$(printf "%s\\n" "$L" | cut -d"|" -f2 | awk "{s+=\\$1} END {print s+0}"); '
           'echo "$n|$c|$b"; done')
    out = subprocess.run([SSH, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", HOST, cmd],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"미니PC 접속 실패: {out.stderr.strip()[:200]}")
    inv: dict[str, tuple[int, int]] = {}
    for line in out.stdout.splitlines():
        if line.count("|") == 2:
            name, c, b = line.rsplit("|", 2)
            name = name.strip()
            if name and name not in SKIP:
                inv[name] = (int(c), int(b))
    return inv


def local_inventory() -> dict[str, tuple[int, int]]:
    inv: dict[str, tuple[int, int]] = {}
    if not LOCAL.exists():
        return inv
    for p in LOCAL.iterdir():
        if not p.is_dir() or p.name in SKIP:
            continue
        # 원격과 같은 규칙 — 트랙번호로 시작하는 mp3 만 센다
        files = [f for f in p.rglob("*.mp3") if f.name[:1].isdigit()]
        inv[p.name] = (len(files), sum(f.stat().st_size for f in files))
    return inv


def fetch(names: list[str]) -> None:
    """tar 로 통째로 받아 로컬에 푼다. 기존 폴더는 덮어쓰지 않고 없는 것만 채운다."""
    quoted = " ".join(shlex.quote(n) for n in names)
    remote_cmd = f"cd {shlex.quote(REMOTE)} && tar cf - {quoted}"
    LOCAL.mkdir(parents=True, exist_ok=True)
    ssh = subprocess.Popen([SSH, "-o", "BatchMode=yes", HOST, remote_cmd], stdout=subprocess.PIPE)
    tar = subprocess.Popen(["tar", "xf", "-"], stdin=ssh.stdout, cwd=str(LOCAL))
    if ssh.stdout:
        ssh.stdout.close()
    tar.communicate()
    ssh.wait()
    if tar.returncode != 0 or ssh.returncode != 0:
        raise RuntimeError(f"전송 실패 (ssh={ssh.returncode}, tar={tar.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        remote = remote_inventory()
    except RuntimeError as e:
        print(f"[에러] {e}")
        print("  미니PC 가 꺼져 있거나 네트워크가 끊겼을 수 있습니다.")
        return 1
    local = local_inventory()

    missing = sorted(n for n in remote if n not in local)
    changed = sorted(n for n in remote if n in local and remote[n] != local[n])
    local_only = sorted(n for n in local if n not in remote)

    print(f"미니PC {len(remote)}개 · 데스크탑 {len(local)}개")
    print(f"  새 앨범        {len(missing)}개")
    print(f"  내용 달라짐    {len(changed)}개")
    print(f"  데스크탑에만   {len(local_only)}개 (건드리지 않음)")

    for n in missing:
        print(f"     + {n}  ({remote[n][0]}곡)")
    for n in changed:
        print(f"     ~ {n}  미니PC {remote[n][0]}곡 / 여기 {local[n][0]}곡")

    todo = missing + changed
    if not todo:
        print("\n받을 것이 없습니다. 이미 최신입니다.")
        return 0
    if args.dry_run:
        print(f"\n(--dry-run: {len(todo)}개를 받을 예정이었습니다)")
        return 0

    total_mb = sum(remote[n][1] for n in todo) / 1024 / 1024
    print(f"\n{len(todo)}개 앨범 전송 시작 (약 {total_mb:.0f}MB) …")
    fetch(todo)

    after = local_inventory()
    ok = sum(1 for n in todo if after.get(n) == remote[n])
    print(f"전송 완료 — {ok}/{len(todo)}개 일치 확인")
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())

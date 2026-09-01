"""
환경 해석 — 같은 코드가 데스크탑(윈도우)과 미니PC(리눅스) 양쪽에서 돌게 한다.

앨범 원본 정본은 미니PC 다. 데스크탑에서 돌릴 땐 사본을 보고, 미니PC에서 돌릴 땐 원본을 본다.
자격증명은 있는 곳에서 읽는다 — 미니PC 는 ~/.config/nexis/r2.env, 데스크탑은 vault.env.
어느 쪽이든 **값은 메모리에만 두고 출력하지 않는다.**

환경변수로 덮어쓸 수 있다:
    JUKEBOX_INPUT_DIR   앨범 원본 폴더
    JUKEBOX_ENV_FILE    R2 자격증명 파일
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# 미니PC(원본 정본) / 데스크탑(사본)
MINIPC_INPUT = Path("/mnt/external/suno-playlist/input")
DESKTOP_INPUT = Path(r"d:/YH/APP/youtube-playlist/suno-playlist-video/input")

# 자격증명 후보 — 앞에서부터 존재하는 것을 쓴다
SECRET_CANDIDATES = [
    Path.home() / ".config" / "nexis" / "r2.env",          # 미니PC
    Path(r"d:/YH/APP/nexis-lab-home/vault.env"),           # 데스크탑(넥시스랩 금고)
]

REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET", "R2_PUBLIC_BASE")


def input_dir() -> Path:
    override = os.environ.get("JUKEBOX_INPUT_DIR")
    if override:
        return Path(override)
    if MINIPC_INPUT.exists():
        return MINIPC_INPUT
    return DESKTOP_INPUT


def is_source_host() -> bool:
    """앨범 원본이 이 기계에 직접 있는가 = 미니PC 인가.
    참이면 sync 단계가 필요 없다(자기 자신에게서 받아올 것이 없다)."""
    return input_dir() == MINIPC_INPUT


def secrets_file() -> Path | None:
    override = os.environ.get("JUKEBOX_ENV_FILE")
    if override:
        p = Path(override)
        return p if p.exists() else None
    for p in SECRET_CANDIDATES:
        if p.exists():
            return p
    return None


def load_secrets() -> dict[str, str]:
    """R2 자격증명을 읽는다. vault 는 UTF-8 BOM 이라 utf-8-sig 로 읽어야 한다.
    반환값에는 실제 값이 들어 있으므로 절대 print 하지 말 것."""
    p = secrets_file()
    if p is None:
        raise RuntimeError(
            "R2 자격증명 파일을 찾을 수 없습니다.\n"
            "  미니PC: ~/.config/nexis/r2.env\n"
            "  데스크탑: d:/YH/APP/nexis-lab-home/vault.env\n"
            "  또는 환경변수 JUKEBOX_ENV_FILE 로 지정하세요.")
    text = p.read_text(encoding="utf-8-sig")
    vals = {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", text, re.M)}
    missing = [k for k in REQUIRED if not vals.get(k)]
    if missing:
        raise RuntimeError(f"자격증명 파일에 비어 있는 슬롯: {', '.join(missing)}")
    return vals

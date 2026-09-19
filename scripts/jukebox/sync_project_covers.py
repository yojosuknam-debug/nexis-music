"""
Replace generated album placeholder covers with miniPC project thumbnails.

The music site catalog can contain albums whose cover is only a generated
typographic/gradient placeholder. For finished video projects, miniPC keeps the
real generated thumbnail at:

    /mnt/external/suno-playlist/output/*_project/thumbnail.png

This script matches those projects to generated-cover albums, pulls the
thumbnail, converts it into the site's 800x800 cover format, and updates the
cover metadata so later asset preparation does not overwrite it.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"
COVERS = HERE / "assets" / "covers"
META = COVERS / "_meta.json"
SIZE = 800

SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
SCP = r"C:\Windows\System32\OpenSSH\scp.exe"
HOST = "minipc"
REMOTE_OUTPUT = "/mnt/external/suno-playlist/output"


REMOTE_INVENTORY = r"""
python3 - <<'PY'
import json
from pathlib import Path

root = Path('/mnt/external/suno-playlist/output')
items = []
for meta_path in sorted(root.glob('*/project_meta.json')):
    project = meta_path.parent
    thumb = project / 'thumbnail.png'
    if not thumb.exists():
        continue
    try:
        data = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception:
        data = {}
    items.append({
        'project_dir': str(project),
        'folder': project.name,
        'thumbnail': str(thumb),
        'album_name': data.get('album_name', ''),
        'artist': data.get('artist', ''),
        'input_dir': data.get('input_dir', ''),
    })
print(json.dumps(items, ensure_ascii=False))
PY
"""


SUFFIX_PATTERNS = [
    r"\s+[—-]\s+lo[- ]?fi\s*&?\s*chill\s+album$",
    r"\s+[—-]\s+still\s+waters\s+album$",
    r"\s+[—-]\s+lofi\s+channel\s+album$",
    r"\s+[—-]\s+hanguk\s+sounds\s+album$",
    r"\s+[—-]\s+korean\s+wind\s+instrument\s+solo\s+series$",
    r"\s+lo[- ]?fi\s+chill\s+album$",
    r"\s+still\s+waters\s+album$",
    r"\s+lofi\s+channel\s+album$",
    r"\s+channel\s+album$",
    r"\s+album$",
]


def ascii_fold(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def words(text: str) -> list[str]:
    text = ascii_fold(text).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[_/\\:·]+", " ", text)
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    return [w for w in text.split() if w]


def key(text: str) -> str:
    return "".join(words(text))


def strip_suffixes(text: str) -> str:
    out = ascii_fold(text).lower().replace("_", " ").replace("-", " ")
    out = re.sub(r"\s+", " ", out).strip()
    for pat in SUFFIX_PATTERNS:
        out = re.sub(pat, "", out, flags=re.I).strip()
    return out


def variants(text: str) -> set[str]:
    out: set[str] = set()
    if not text:
        return out
    candidates = {text, strip_suffixes(text)}
    candidates.update(re.findall(r"\(([^)]+)\)", text))
    for sep in ["—", " - ", " / ", ":"]:
        if sep in text:
            candidates.update(part.strip() for part in text.split(sep) if part.strip())
    for item in candidates:
        k = key(item)
        if k:
            out.add(k)
    return out


def album_keys(album: dict) -> set[str]:
    fields = [
        album.get("title", ""),
        album.get("slug", ""),
        album.get("folder", ""),
        Path(album.get("cover_file", "")).stem,
    ]
    keys: set[str] = set()
    for field in fields:
        keys.update(variants(field))
    return keys


def project_keys(project: dict) -> set[str]:
    fields = [
        project.get("album_name", ""),
        project.get("folder", "").removesuffix("_project"),
        Path(project.get("input_dir", "")).name,
    ]
    keys: set[str] = set()
    for field in fields:
        keys.update(variants(field))
    return keys


def score_keys(left: set[str], right: set[str]) -> float:
    best = 0.0
    for a in left:
        for b in right:
            if not a or not b:
                continue
            if a == b:
                return 1.0
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            shorter, longer = sorted((a, b), key=len)
            if len(shorter) >= 6 and shorter in longer:
                ratio = max(ratio, len(shorter) / len(longer) + 0.18)
            best = max(best, min(ratio, 0.99))
    return best


def load_remote_projects() -> list[dict]:
    proc = subprocess.run(
        [SSH, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", HOST, REMOTE_INVENTORY],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "ssh inventory failed")
    return json.loads(proc.stdout)


def fetch_thumbnail(remote_path: str, local_path: Path) -> None:
    # subprocess passes this as a single local argument, so shell metacharacters
    # in the remote path are not interpreted locally. Quoting here breaks
    # OpenSSH's SFTP-backed scp path handling on Windows for non-ASCII names.
    remote_arg = f"{HOST}:{remote_path}"
    proc = subprocess.run(
        [SCP, "-q", remote_arg, str(local_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"scp failed: {remote_path}")


def square_thumbnail(src: Path, dst: Path) -> None:
    im = Image.open(src).convert("RGB")
    bg_w = round(SIZE * im.width / im.height)
    if bg_w < SIZE:
        bg_w = SIZE
    bg = im.resize((bg_w, SIZE), Image.LANCZOS)
    left = (bg.width - SIZE) // 2
    bg = bg.crop((left, 0, left + SIZE, SIZE)).filter(ImageFilter.GaussianBlur(18))
    bg = ImageEnhance.Brightness(bg).enhance(0.62)

    fg_h = round(SIZE * im.height / im.width)
    fg = im.resize((SIZE, fg_h), Image.LANCZOS)
    canvas = bg.copy()
    canvas.paste(fg, (0, (SIZE - fg_h) // 2))
    canvas.save(dst, "JPEG", quality=92, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.82)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    albums = json.loads(CATALOG.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    generated = [a for a in albums if meta.get(a["slug"], {}).get("kind") == "generated"]
    projects = load_remote_projects()
    pkey = {p["thumbnail"]: project_keys(p) for p in projects}

    matches: list[tuple[float, dict, dict]] = []
    misses: list[tuple[float, dict, dict | None]] = []
    used: set[str] = set()

    for album in generated:
        akeys = album_keys(album)
        ranked = sorted(
            ((score_keys(akeys, pkey[p["thumbnail"]]), p) for p in projects),
            key=lambda item: item[0],
            reverse=True,
        )
        score, project = ranked[0] if ranked else (0.0, None)
        if project and score >= args.threshold and project["thumbnail"] not in used:
            used.add(project["thumbnail"])
            matches.append((score, album, project))
        else:
            misses.append((score, album, project))

    print(f"generated covers: {len(generated)}")
    print(f"matched thumbnails: {len(matches)}")
    print(f"unmatched: {len(misses)}")

    for score, album, project in matches:
        print(f"  {score:.2f}  {album['slug']}  <=  {project['folder']}")
    if misses:
        print("\nunmatched generated covers:")
        for score, album, project in misses:
            near = project["folder"] if project else "-"
            print(f"  {score:.2f}  {album['slug']}  nearest={near}")

    if args.dry_run:
        return 0

    changed = 0
    with tempfile.TemporaryDirectory(prefix="project-covers-") as td:
        tmp = Path(td)
        for score, album, project in matches:
            cover = COVERS / album["cover_file"]
            before = cover.read_bytes() if cover.exists() else b""
            thumb = tmp / f"{hashlib.sha256(project['thumbnail'].encode('utf-8')).hexdigest()}.png"
            fetch_thumbnail(project["thumbnail"], thumb)
            square_thumbnail(thumb, cover)
            after = cover.read_bytes()
            if before != after:
                changed += 1
            meta[album["slug"]] = {
                "kind": "project_thumbnail",
                "src": project["thumbnail"],
                "project": project["folder"],
                "match_score": round(score, 3),
            }

    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nupdated cover files: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

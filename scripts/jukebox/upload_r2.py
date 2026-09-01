"""
3단계 — R2 업로드

catalog.json 의 mp3·커버를 Cloudflare R2 로 올리고, 공개 URL 을 catalog 에 되쓴다.

  audio/<slug>/<NN>.mp3     음원
  cover/<slug>.jpg          커버

재실행 안전하다. 이미 올라간 파일은 **크기가 같으면 건너뛴다**. 중간에 끊겨도 다시 돌리면 이어서 한다.
자격증명은 vault.env 에서 메모리로만 읽고 어디에도 출력하지 않는다.

사용법:
    python scripts/jukebox/upload_r2.py            # 올린다
    python scripts/jukebox/upload_r2.py --dry-run  # 무엇을 올릴지만 계산
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import _env

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"
COVERS = HERE / "assets" / "covers"

WORKERS = 6
# 파일 이름에 슬러그(불변)가 들어가고 내용이 바뀌면 이름도 바뀌므로 길게 캐시해도 안전하다
CACHE = "public, max-age=31536000, immutable"


def load_vault() -> dict[str, str]:
    """자격증명을 읽는다. 미니PC 는 ~/.config/nexis/r2.env, 데스크탑은 vault.env.
    값은 메모리에만 두고 어디에도 출력하지 않는다."""
    return _env.load_secrets()


def client(v: dict[str, str]):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{v['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=v["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=v["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 4, "mode": "standard"}),
    )


def remote_size(s3, bucket: str, key: str) -> int | None:
    try:
        return s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def plan(albums: list[dict]) -> list[tuple[Path, str, str]]:
    """(로컬경로, R2키, ContentType) 목록을 만든다."""
    jobs: list[tuple[Path, str, str]] = []
    for a in albums:
        cover = COVERS / a.get("cover_file", "")
        if a.get("cover_file") and cover.exists():
            jobs.append((cover, f"cover/{a['slug']}.jpg", "image/jpeg"))
        for t in a["tracks"]:
            if not t.get("src"):
                continue
            p = Path(t["src"])
            if p.exists():
                jobs.append((p, f"audio/{a['slug']}/{t['n']:02d}.mp3", "audio/mpeg"))
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CATALOG.exists():
        print("[에러] catalog.json 이 없습니다. scan_albums.py 를 먼저 실행하세요.")
        return 1

    v = load_vault()
    need = [k for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                        "R2_BUCKET", "R2_PUBLIC_BASE") if not v.get(k)]
    if need:
        print("[에러] vault.env 에 비어 있는 슬롯:", ", ".join(need))
        return 1

    albums = json.loads(CATALOG.read_text(encoding="utf-8"))
    bucket = v["R2_BUCKET"]
    base = v["R2_PUBLIC_BASE"].rstrip("/")
    s3 = client(v)
    jobs = plan(albums)
    total_bytes = sum(p.stat().st_size for p, _, _ in jobs)

    print(f"대상 {len(jobs)}개 파일 · {total_bytes/1024/1024/1024:.2f} GB")
    if args.dry_run:
        print("(--dry-run: 실제 업로드는 하지 않습니다)")
        return 0

    lock = threading.Lock()
    stat = {"up": 0, "skip": 0, "fail": 0, "bytes": 0}

    def work(job):
        path, key, ctype = job
        size = path.stat().st_size
        try:
            if remote_size(s3, bucket, key) == size:
                with lock:
                    stat["skip"] += 1
                return
            with path.open("rb") as fh:
                s3.upload_fileobj(fh, bucket, key,
                                  ExtraArgs={"ContentType": ctype, "CacheControl": CACHE})
            with lock:
                stat["up"] += 1
                stat["bytes"] += size
        except Exception as e:                       # 한 파일이 죽어도 전체는 계속한다
            with lock:
                stat["fail"] += 1
            return f"{key}: {type(e).__name__}"

    errors = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(work, j) for j in jobs]
        for f in as_completed(futures):
            done += 1
            err = f.result()
            if err:
                errors.append(err)
            if done % 50 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}  올림 {stat['up']} · 건너뜀 {stat['skip']} · "
                      f"실패 {stat['fail']} · 전송 {stat['bytes']/1024/1024:.0f}MB", flush=True)

    for a in albums:
        if a.get("cover_file"):
            # 커버는 파일 이름이 그대로라, 내용이 바뀌어도 1년 캐시 때문에 옛 그림이 계속 보인다.
            # 내용 해시를 쿼리로 붙여 바뀐 커버는 새 주소가 되게 한다(Cloudflare 는 쿼리까지 보고 캐시).
            cf = COVERS / a["cover_file"]
            tag = hashlib.sha256(cf.read_bytes()).hexdigest()[:8] if cf.exists() else "0"
            a["cover_url"] = f"{base}/cover/{a['slug']}.jpg?v={tag}"
        for t in a["tracks"]:
            if t.get("src"):
                t["url"] = f"{base}/audio/{a['slug']}/{t['n']:02d}.mp3"
    CATALOG.write_text(json.dumps(albums, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n완료 — 업로드 {stat['up']} · 건너뜀 {stat['skip']} · 실패 {stat['fail']}")
    if errors:
        print("실패 목록(앞 10개):")
        for e in errors[:10]:
            print("   ", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

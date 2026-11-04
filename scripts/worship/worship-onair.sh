#!/bin/bash
# 매일 온라인 예배 한 회차 송출 — 미니PC 크론(예배 5분 전). 자세한 규칙은 worship_onair.py.
#   55 3,9,15,21 * * * flock -n /tmp/worship-onair-ko.lock bash .../worship-onair.sh ko >/dev/null 2>&1  # nexis-worship-onair
#   55 0,6,12,18 * * * flock -n /tmp/worship-onair-en.lock bash .../worship-onair.sh en >/dev/null 2>&1  # nexis-worship-onair
set -u
L=${1:?ko|en}
shift
B=/mnt/external/nexis-worship
W=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$B/logs"
exec >>"$B/logs/onair-$(date +%F).log" 2>&1
echo "===== $(date '+%F %T') [$L] 회차 시작"
"$B/.venv/bin/python" -u "$W/worship_onair.py" "$L" "$@"
rc=$?
echo "===== $(date '+%F %T') [$L] 끝 (exit $rc)"
exit $rc

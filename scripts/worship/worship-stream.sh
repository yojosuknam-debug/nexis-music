#!/bin/bash
# 실시간 예배 송출 — 미리 만든 영상을 그대로(재인코딩 없이) 유튜브로 보낸다. 미니PC 크론.
#   55 5  * * * bash /mnt/external/nexis-music/scripts/worship/worship-stream.sh ko   # nexis-worship-stream
#   55 10 * * * bash /mnt/external/nexis-music/scripts/worship/worship-stream.sh en   # nexis-worship-stream
# 5분 대기 화면이 영상 앞에 들어 있어 예배는 06:00·11:00 정각에 시작한다.
# 방송은 자동 시작·자동 종료 → 끝나면 유튜브가 같은 주소의 영상으로 저장(제목·챕터·재생목록은 예약 때 넣어 둠).
set -u
L=${1:?ko|en}
B=/mnt/external/nexis-worship
D=$(date +%F)
F="$B/output/${D}_$L/worship_${D}_$L.mp4"
exec >>"$B/logs/stream-$D.log" 2>&1
echo "===== $(date '+%F %T') [$L] 송출"
[ -s "$F" ] || { echo "영상 없음: $F"; exit 0; }
[ -s "$B/streamkey_$L" ] || { echo "스트림 키 없음(예약 실패)"; exit 0; }
URL=$(cat "$B/streamkey_$L")
ffmpeg -hide_banner -loglevel error -nostdin -re -i "$F" -c copy -f flv "$URL" 2>&1 \
  | sed -E 's#(rtmps?://[^ ]*/)[^ ]+#\1***#g'
echo "===== $(date '+%F %T') [$L] 끝 (exit ${PIPESTATUS[0]})"

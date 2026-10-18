#!/bin/bash
# yojosuknam Radio 유튜브 라이브 채팅에 '지금 곡 원곡 링크' 1건 (미니PC 크론, 3시간마다)
#   크론: 7 */3 * * * bash /mnt/external/nexis-music/scripts/radio/youtube-chat.sh   # nexis-radio-youtube-chat
# - chat_post.py 를 autovid-bot 컨테이너(nexis-horror 토큰)에서 돌린다. 1회 ≈ 51단위, 하루 8회 ≈ 410단위
# - 진행 중인 방송이 없으면 로그에 '방송 없음'(라이브 꺼짐 감시 겸용)
# 토큰은 화면·로그에 찍지 않는다.
set -u
LOG=/mnt/external/nexis-music-radio-youtube-chat.log
CH=/mnt/external/nexis-music/scripts/radio/youtube-channel

exec >>"$LOG" 2>&1
echo "===== $(date '+%F %T')"
docker cp "$CH/chat_post.py" autovid-bot:/tmp/chat_post.py >/dev/null || { echo "docker cp 실패"; exit 0; }
docker exec autovid-bot python /tmp/chat_post.py "$@" 2>&1 \
  | sed -E 's/ya29\.[A-Za-z0-9._-]+/***/g; s#1//[A-Za-z0-9._-]+#***#g' | tail -4
docker exec autovid-bot rm -f /tmp/chat_post.py
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"     # 로그는 최근 400줄만

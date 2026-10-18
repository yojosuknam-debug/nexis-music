#!/bin/bash
# yojosuknam Radio 유튜브 라이브 채팅 — 편성(채널·장르)이 바뀔 때만 '지금 장르 + 채널 주소' 1건 (미니PC 크론, 5분마다)
#   크론: */5 * * * * bash /mnt/external/nexis-music/scripts/radio/youtube-chat.sh   # nexis-radio-youtube-chat
#   수동: youtube-chat.sh --desc  → 라이브 설명란 다시 적용 / youtube-chat.sh --song → 지금 곡 원곡 링크 1건
# - 바뀌었는지는 nowplaying.json 의 지금 곡 채널로 본다(할당량 0). 바뀐 때만 chat_post.py 를 autovid-bot(nexis-horror 토큰)에서 돌린다.
#   1회 ≈ 51단위, 편성 전환 하루 약 23회 ≈ 1,200단위(하루 10,000, autovid 와 공유)
# - 진행 중인 방송이 없으면 로그에 '방송 없음'(라이브 꺼짐 감시 겸용)
# 토큰은 화면·로그에 찍지 않는다.
set -u
LOG=/mnt/external/nexis-music-radio-youtube-chat.log
STATE=~/.radio-chat-station
R=/mnt/external/nexis-music/scripts/radio
NOW_URL=https://audio.yojosuknam.com/radio/nowplaying.json

mode=--program
case "${1:-}" in
  --desc) mode=--desc ;;
  --song) mode="" ;;
  *)
    st=$(curl -fsS --max-time 15 "$NOW_URL" | jq -r '.now.station // empty') || exit 0
    [ -n "$st" ] || exit 0
    [ "$st" = "$(cat "$STATE" 2>/dev/null)" ] && exit 0
    ;;
esac

exec >>"$LOG" 2>&1
echo "===== $(date '+%F %T') ${mode:-지금 곡} ${st:-}"
for f in youtube-channel/chat_post.py schedule.py schedule.json; do
  docker cp "$R/$f" "autovid-bot:/tmp/$(basename "$f")" >/dev/null || { echo "docker cp 실패: $f"; exit 0; }
done
[ "$mode" = --desc ] && docker cp "$R/youtube-channel/setup_channel.py" autovid-bot:/tmp/setup_channel.py >/dev/null
out=$(docker exec autovid-bot python /tmp/chat_post.py $mode 2>&1 \
  | sed -E 's/ya29\.[A-Za-z0-9._-]+/***/g; s#1//[A-Za-z0-9._-]+#***#g' | tail -4)
echo "$out"
docker exec autovid-bot rm -f /tmp/chat_post.py /tmp/schedule.py /tmp/schedule.json /tmp/setup_channel.py
# 올렸거나 방송이 없을 때 상태 기록(실패면 다음 5분에 다시)
if [ "$mode" = --program ] && echo "$out" | grep -qE "채팅 올림|방송 없음"; then echo "$st" > "$STATE"; fi
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"     # 로그는 최근 400줄만

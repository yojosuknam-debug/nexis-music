#!/bin/bash
# yojosuknam Radio 유튜브 라이브 — 라이브 권한이 풀리면 자동으로 켠다 (미니PC 크론, 30분마다)
#   크론: */30 * * * * bash /mnt/external/nexis-music/scripts/radio/youtube-go.sh   # nexis-radio-youtube-go
# - NOT_BEFORE 전에는 아무것도 안 한다(유튜브 24시간 대기)
# - setup_channel.py(autovid-bot 컨테이너, nexis-horror 토큰)로 라이브 방송·스트림을 만들고
#   스트림 키를 radio.env 로 옮긴 뒤 유튜브 송출기 컨테이너를 켠다
# - 성공하면 ~/.radio-youtube-done 을 만들고 크론 줄을 스스로 지운다. GIVE_UP 이후에도 지운다
# 스트림 키는 화면·로그에 찍지 않는다.
set -u
NOT_BEFORE="2026-10-19 01:25"
GIVE_UP="2026-10-20 06:00"   # 할당량 보호: 재시도 1회 ≈ 51단위, 하루 한도 10,000(autovid 와 공유)
MARK="nexis-radio-youtube-go"
LOG=/mnt/external/nexis-music-radio-youtube-go.log
DONE=~/.radio-youtube-done
ENVF=~/.config/nexis/radio.env
REPO=/mnt/external/nexis-music
CH="$REPO/scripts/radio/youtube-channel"

remove_cron() { crontab -l 2>/dev/null | grep -v "$MARK" | crontab -; echo "크론 줄 삭제"; }

exec >>"$LOG" 2>&1
now=$(date +%s)
[ -f "$DONE" ] && { remove_cron; exit 0; }
[ "$now" -lt "$(date -d "$NOT_BEFORE" +%s)" ] && exit 0
echo "===== $(date '+%F %T')"
if [ "$now" -ge "$(date -d "$GIVE_UP" +%s)" ]; then echo "기한 지남 — 포기"; remove_cron; exit 0; fi

cd "$REPO" && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"
for f in setup_channel.py banner-2560x1440.jpg thumb-1280x720.jpg; do
  docker cp "$CH/$f" "autovid-bot:/tmp/$f" >/dev/null || { echo "docker cp 실패: $f"; exit 0; }
done
docker exec autovid-bot python /tmp/setup_channel.py --live-only 2>&1 \
  | sed -E 's/ya29\.[A-Za-z0-9._-]+/***/g; s#1//[A-Za-z0-9._-]+#***#g' | tail -4
if docker exec autovid-bot test -s /tmp/ytkey; then
  { grep -v '^YOUTUBE_STREAM_KEY=' "$ENVF"; printf 'YOUTUBE_STREAM_KEY='; docker exec autovid-bot cat /tmp/ytkey; echo; } > "$ENVF.tmp" \
    && chmod 600 "$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
  docker exec autovid-bot rm -f /tmp/ytkey
  echo "스트림 키 → radio.env"
  cd "$REPO/scripts/radio" && docker compose --profile youtube up -d --build radio-youtube 2>&1 | tail -3
  sleep 60
  docker ps --filter name=nexis-radio-youtube --format '{{.Names}} {{.Status}}'
  docker logs --tail 5 nexis-radio-youtube 2>&1 | grep -v '^$'
  touch "$DONE"
  remove_cron
  echo "✅ 유튜브 라이브 송출 시작"
else
  echo "아직 라이브 권한 없음 — 30분 뒤 다시"
fi
docker exec autovid-bot rm -f /tmp/setup_channel.py /tmp/banner-2560x1440.jpg /tmp/thumb-1280x720.jpg /tmp/ytkey

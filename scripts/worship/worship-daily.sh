#!/bin/bash
# ⚠️ 옛 방식(미니PC 가 목소리까지 — 한 편 약 5시간). 10-24 부터는 나눠 맡는다:
#    맥미니 worship-mac.sh(원고·목소리) → 미니PC worship-assemble.sh(조립·방송 예약). 이 파일은 비상용으로만 둔다.
# 다음날 실시간 예배 두 편(한국어·영어) 만들기 + 방송 예약 — 미니PC 크론, 매일 21:30
#   크론: 30 21 * * * bash /mnt/external/nexis-music/scripts/worship/worship-daily.sh   # nexis-worship-daily
# 순서: 한국어 원고 → 같은 원고 영어판 → 각 언어 음성(내 목소리·Chatterbox, nice) → 찬양과 합치기 → 화면·영상 → 방송 예약
# 음성 제작은 CPU 를 오래 쓰므로 nice 15 + 스레드 3(다른 서비스 몫을 남긴다). 스트림 키는 화면·로그에 찍지 않는다.
set -u
B=/mnt/external/nexis-worship
REPO=/mnt/external/nexis-music
W="$REPO/scripts/worship"
export WORSHIP_OUT=$B/output WORSHIP_REF_DIR=$B/ref WORSHIP_BG_DIR=$HOME/autovid/assets/qt_images
export WORSHIP_THREADS=3 HF_HOME=$B/hf PYTHONIOENCODING=utf-8
# 한국어 원고 바탕 = 말씀Log 큐티 2,000개 — qt-insta 와 같은 파일·순서표(같은 날 같은 본문)
export WORSHIP_QT_DATA=$HOME/autovid/data/qt_data.json WORSHIP_QT_ELIGIBLE=$HOME/qt-insta/data/eligible_ids.json
D=$(date -d tomorrow +%F)
mkdir -p "$B/logs" "$WORSHIP_OUT"
exec >>"$B/logs/daily-$D.log" 2>&1
echo "===== $(date '+%F %T') 예배 $D 준비"
cd "$REPO" && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"
PY="nice -n 15 ionice -c3 $B/.venv/bin/python -u"

for L in ko en; do
  O="$WORSHIP_OUT/${D}_$L"
  $PY "$W/build_worship.py" --lang $L --date "$D" --voice --mix \
    | grep -v -E "it/s|s/it|Warning|deprecat|forcing EOS" || true
  [ -s "$O/worship_${D}_$L.mp3" ] || { echo "[$L] 음성 제작 실패 — 이 언어는 오늘 건너뜀"; continue; }
  $PY "$W/render_video.py" "$O" --preroll 300 || { echo "[$L] 영상 실패"; continue; }
  $B/.venv/bin/python "$W/live_spec.py" "$O" --preroll 300 > "$O/spec.json" || continue
  docker cp "$W/worship_live.py" autovid-bot:/tmp/worship_live.py >/dev/null
  docker cp "$O/spec.json" "autovid-bot:/tmp/worship_spec_$L.json" >/dev/null
  docker exec autovid-bot python /tmp/worship_live.py schedule "/tmp/worship_spec_$L.json" \
    | sed -E 's/ya29\.[A-Za-z0-9._-]+/***/g' | tee "$O/broadcast.json"
  if docker exec autovid-bot test -s "/tmp/worship_streamkey_$L"; then
    ( umask 077; docker exec autovid-bot cat "/tmp/worship_streamkey_$L" > "$B/streamkey_$L" )
    docker exec autovid-bot rm -f "/tmp/worship_streamkey_$L"
    echo "[$L] 방송 예약 완료"
  else
    echo "[$L] 방송 예약 실패"
  fi
done
echo "===== $(date '+%F %T') 끝"

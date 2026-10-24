#!/bin/bash
# 미니PC 몫 — 맥미니가 보낸 목소리 묶음으로 조립(찬송·기도회 배경 합치기 → 자막 화면 → 영상) → (선택) 유튜브 방송 예약.
#   bash /mnt/external/nexis-music/scripts/worship/worship-assemble.sh [날짜=내일] ["ko en"]
#   SCHEDULE=1 bash …  → 조립 뒤 유튜브 라이브 예약까지(기본은 하지 않음 — 10-24 사용자: 수동 시험까지만)
# 송출은 그대로 worship-stream.sh(05:55 ko · 10:55 en). 매일 자동 실행(크론)은 아직 등록하지 않는다.
# 목소리 묶음 위치: /mnt/external/macmini/<이관 묶음>/worship-voice/<날짜>_<언어>/ (맥미니 worship-mac.sh → archive-outbox.sh)
set -u
B=/mnt/external/nexis-worship
REPO=/mnt/external/nexis-music
W="$REPO/scripts/worship"
export WORSHIP_OUT=$B/output WORSHIP_REF_DIR=$B/ref WORSHIP_BG_DIR=$HOME/autovid/assets/qt_images
export WORSHIP_MUSIC_DIR=$B/music PYTHONIOENCODING=utf-8
D=${1:-$(date -d tomorrow +%F)}
LANGS=${2:-"ko en"}
SCHEDULE=${SCHEDULE:-0}
mkdir -p "$B/logs" "$WORSHIP_OUT" "$WORSHIP_MUSIC_DIR"
exec > >(tee -a "$B/logs/assemble-$D.log") 2>&1
echo "===== $(date '+%F %T') 예배 $D ($LANGS) 미니PC 조립 · 방송 예약 $([ "$SCHEDULE" = 1 ] && echo 함 || echo '안 함')"
cd "$REPO" && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"
PY="nice -n 10 $B/.venv/bin/python -u"
for L in $LANGS; do
  O="$WORSHIP_OUT/${D}_$L"
  T0=$(date +%s)
  BUN=$($PY "$W/voice_bundle.py" find /mnt/external/macmini "${D}_$L") || { echo "[$L] $BUN — 건너뜀"; continue; }
  $PY "$W/voice_bundle.py" unpack "$BUN" "$O" || { echo "[$L] 묶음 풀기 실패"; continue; }
  $PY "$W/build_worship.py" --lang $L --date "$D" --mix || { echo "[$L] 합치기 실패"; continue; }
  $PY "$W/render_video.py" "$O" --preroll 300 || { echo "[$L] 영상 실패"; continue; }
  $B/.venv/bin/python "$W/live_spec.py" "$O" --preroll 300 > "$O/spec.json" || { echo "[$L] 방송 정보 실패"; continue; }
  echo "[$L] 조립 완료 $(( ($(date +%s)-T0)/60 ))분 · $O/worship_${D}_$L.mp4"
  [ "$SCHEDULE" = 1 ] || { echo "[$L] 방송 예약은 건너뜀(SCHEDULE=1 일 때만)"; continue; }
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

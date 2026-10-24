#!/bin/bash
# 맥미니 몫 — 예배 원고 + 내 목소리 낭독(Chatterbox·Apple GPU)만 만들어 미니PC 로 보낸다(10-24 사용자 결정: 나눠 맡기).
#   bash scripts/worship/worship-mac.sh [날짜=내일] ["ko en"]
#   FULL=1 bash … → 예전처럼 맥미니에서 합치기·영상까지(시험·비교용)
# 미니PC(CPU)는 낭독이 실시간의 약 20배라 목소리는 맥미니가, 조립(합치기·자막 화면·영상)·방송 예약·송출은
# 방송을 원래 맡던 미니PC 가 한다 → scripts/worship/worship-assemble.sh.
# 목소리 묶음(voice_bundle.py pack)은 ~/Work/outbox/worship-voice/<날짜>_<언어>/ 에 넣고, archive-outbox.sh(10분 주기)가
# 미니PC /mnt/external/macmini/<이관 묶음>/worship-voice/ 로 옮긴 뒤 검증되면 맥에서 지운다.
set -u
B=$HOME/Work/nexis-worship
REPO=$HOME/Work/nexis-music
W="$REPO/scripts/worship"
OUTBOX=$HOME/Work/outbox
export WORSHIP_OUT=$B/output WORSHIP_REF_DIR=$B/ref WORSHIP_BG_DIR=$B/bg
export WORSHIP_DEVICE=mps WORSHIP_THREADS=8 HF_HOME=$B/hf PYTHONIOENCODING=utf-8 PYTORCH_ENABLE_MPS_FALLBACK=1
# 한국어 원고 바탕 = 말씀Log 큐티 2,000개. 미니PC autovid/data/qt_data.json·qt-insta/data/eligible_ids.json 사본
# (10-23 복사). 미니PC 쪽 파일이 바뀌면 다시 복사해야 인스타 카드와 같은 본문이 유지된다.
export WORSHIP_QT_DATA=$B/qt/qt_data.json WORSHIP_QT_ELIGIBLE=$B/qt/eligible_ids.json
export PATH=/opt/homebrew/bin:$PATH
D=${1:-$(date -v+1d +%F)}
LANGS=${2:-"ko en"}
FULL=${FULL:-0}
mkdir -p "$B/logs" "$WORSHIP_OUT"
exec > >(tee -a "$B/logs/mac-$D.log") 2>&1
echo "===== $(date '+%F %T') 예배 $D ($LANGS) 맥미니 $([ "$FULL" = 1 ] && echo '전체 제작' || echo '원고·목소리')"
cd "$REPO" && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"
PY="$B/.venv/bin/python -u"
for L in $LANGS; do
  O="$WORSHIP_OUT/${D}_$L"
  if [ "$FULL" = 1 ]; then
    $PY "$W/build_worship.py" --lang $L --date "$D" --voice --mix | grep -v -E "it/s|s/it|Warning|deprecat|forcing EOS" || true
    [ -s "$O/worship_${D}_$L.mp3" ] || { echo "[$L] 제작 실패 — 건너뜀"; continue; }
    $PY "$W/render_video.py" "$O" --preroll 300 || { echo "[$L] 영상 실패"; continue; }
    $PY "$W/live_spec.py" "$O" --preroll 300 > "$O/spec.json" || true
    T="$OUTBOX/worship/${D}_$L"
    mkdir -p "$T" && cp "$O/worship_${D}_$L.mp4" "$O/worship_${D}_$L.mp3" "$O/script.json" "$T/"
    echo "[$L] 전체 제작 완료 → outbox/worship"
    continue
  fi
  $PY "$W/build_worship.py" --lang $L --date "$D" --voice | grep -v -E "it/s|s/it|Warning|deprecat|forcing EOS" || true
  $PY "$W/voice_bundle.py" pack "$O" "$OUTBOX/worship-voice/${D}_$L" \
    && echo "[$L] 목소리 묶음 → outbox/worship-voice (10분 안에 미니PC 외장하드로 이동)" \
    || echo "[$L] 목소리 제작 실패 — 묶음 안 보냄"
done
echo "===== $(date '+%F %T') 끝"

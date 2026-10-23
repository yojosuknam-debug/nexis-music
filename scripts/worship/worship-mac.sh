#!/bin/bash
# 맥미니에서 예배 영상 만들기 — 내 목소리 낭독(Chatterbox·Apple GPU) → 찬양과 합치기 → 화면·영상 → outbox.
#   bash scripts/worship/worship-mac.sh [날짜=내일] ["ko en"]
# 미니PC(CPU)는 낭독이 실시간의 약 20배라 무거운 제작은 맥미니가 맡는다(10-23 사용자 결정).
# 결과(mp4·mp3·script.json·spec.json)는 ~/Work/outbox/worship/<날짜>_<언어>/ 에 넣고,
# archive-outbox.sh(10분 주기)가 미니PC /mnt/external/macmini/<묶음>/worship/ 로 옮긴 뒤 검증되면 맥에서 지운다.
# 방송 예약·송출은 미니PC 몫(worship-daily.sh 예약 부분·worship-stream.sh) — 여기서는 하지 않는다.
set -u
B=$HOME/Work/nexis-worship
REPO=$HOME/Work/nexis-music
W="$REPO/scripts/worship"
OUTBOX=$HOME/Work/outbox/worship
export WORSHIP_OUT=$B/output WORSHIP_REF_DIR=$B/ref WORSHIP_BG_DIR=$B/bg
export WORSHIP_DEVICE=mps WORSHIP_THREADS=8 HF_HOME=$B/hf PYTHONIOENCODING=utf-8 PYTORCH_ENABLE_MPS_FALLBACK=1
# 한국어 원고 바탕 = 말씀Log 큐티 2,000개. 미니PC autovid/data/qt_data.json·qt-insta/data/eligible_ids.json 사본
# (10-23 복사). 미니PC 쪽 파일이 바뀌면 다시 복사해야 인스타 카드와 같은 본문이 유지된다.
export WORSHIP_QT_DATA=$B/qt/qt_data.json WORSHIP_QT_ELIGIBLE=$B/qt/eligible_ids.json
export PATH=/opt/homebrew/bin:$PATH
D=${1:-$(date -v+1d +%F)}
LANGS=${2:-"ko en"}
mkdir -p "$B/logs" "$WORSHIP_OUT" "$OUTBOX"
exec > >(tee -a "$B/logs/mac-$D.log") 2>&1
echo "===== $(date '+%F %T') 예배 $D ($LANGS) 맥미니 제작"
cd "$REPO" && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"
PY="$B/.venv/bin/python -u"
for L in $LANGS; do
  O="$WORSHIP_OUT/${D}_$L"
  $PY "$W/build_worship.py" --lang $L --date "$D" --voice --mix \
    | grep -v -E "it/s|s/it|Warning|deprecat|forcing EOS" || true
  [ -s "$O/worship_${D}_$L.mp3" ] || { echo "[$L] 음성 제작 실패 — 이 언어는 건너뜀"; continue; }
  $PY "$W/render_video.py" "$O" --preroll 300 || { echo "[$L] 영상 실패"; continue; }
  $PY "$W/live_spec.py" "$O" --preroll 300 > "$O/spec.json" || echo "[$L] 방송 정보(spec) 실패 — 영상은 보냄"
  T="$OUTBOX/${D}_$L"
  mkdir -p "$T" && cp "$O/worship_${D}_$L.mp4" "$O/worship_${D}_$L.mp3" "$O/script.json" "$T/"
  [ -s "$O/spec.json" ] && cp "$O/spec.json" "$T/"
  echo "[$L] 완료 → outbox (10분 안에 미니PC 외장하드로 이동)"
done
echo "===== $(date '+%F %T') 끝"

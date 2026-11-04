#!/bin/bash
# 매일 예배 제작 — 미니PC 몫(조립·검증·알림·로그). 맥미니 낭독 묶음이 오면 조립 → worship_verify.py 로 완성 판정 → READY.
#   크론(등록은 사용자 승인 후):
#     40 23 * * * flock -n /tmp/worship-nightly.lock bash /mnt/external/nexis-music/scripts/worship/worship-nightly.sh            # nexis-worship-nightly   (내일 예배)
#     30 5  * * * flock -n /tmp/worship-nightly.lock bash /mnt/external/nexis-music/scripts/worship/worship-nightly.sh --check    # nexis-worship-check    (오늘 예배 점검·조립)
#     20 9  * * * flock -n /tmp/worship-nightly.lock bash /mnt/external/nexis-music/scripts/worship/worship-nightly.sh --deadline # nexis-worship-deadline (09:20 최종 판정)
#   시험: bash worship-nightly.sh --date 2026-11-05 --verify-only --no-notify   (조립·재시도 없이 있는 영상만 판정)
# D일 영상 = D일 10:00 한글부터 D+1일 07:00 영어까지 쓴다(01·04·07시도 전날 영상). 폴더: output/<D>_<ko|en>/ · 완성 표시: READY
# 방송 예약·송출은 이 스크립트가 하지 않는다(다른 창의 worship-stream.sh 몫).
set -u
B=/mnt/external/nexis-worship
W=/mnt/external/nexis-music/scripts/worship
PY=$B/.venv/bin/python
MODE=night; D=""; VERIFY_ONLY=0
RETRY_WAIT=${WORSHIP_RETRY_WAIT:-600}          # 조립 첫 실패 뒤 쉬는 초
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --deadline) MODE=deadline ;;
    --date) D=$2; shift ;;
    --verify-only) VERIFY_ONLY=1 ;;
    --no-notify) export WORSHIP_NOTIFY=0 ;;
  esac
  shift
done
[ -n "$D" ] || { [ "$MODE" = night ] && D=$(date -d tomorrow +%F) || D=$(date +%F); }
mkdir -p "$B/logs"
exec >>"$B/logs/nightly-$D.log" 2>&1
echo "===== $(date '+%F %T') 예배 $D 점검($MODE)"
ev()  { $PY "$W/worship_ops.py" log "$@"; }                  # stage status detail date lang
tell(){ $PY "$W/worship_ops.py" notify "$@"; }
cd /mnt/external/nexis-music && git pull -q --ff-only || echo "(git pull 실패 — 있는 코드로 진행)"

MISSING=(); FAILED=(); READY=()
ensure() {                                                  # 한 언어를 READY 까지
  local L=$1 O="$B/output/${D}_$1" try
  [ -e "$O/READY" ] && { READY+=("$L"); return 0; }
  if [ -s "$O/worship_${D}_$L.mp4" ] && $PY "$W/worship_verify.py" "$O" >/dev/null 2>&1; then
    ev verify ok "기존 영상 통과" "$D" "$L"; READY+=("$L"); return 0
  fi
  if [ "$VERIFY_ONLY" = 1 ]; then
    FAILED+=("$L"); ev verify fail "$(tr -d '\n' < "$O/FAILED.json" 2>/dev/null | cut -c1-180)" "$D" "$L"; return 1
  fi
  local BUN; BUN=$($PY "$W/voice_bundle.py" find /mnt/external/macmini "${D}_$L") \
    || { MISSING+=("$L"); ev voice wait "맥미니 낭독 묶음 아직 없음" "$D" "$L"; return 1; }
  ev voice ok "묶음 도착 $(basename "$(dirname "$(dirname "$BUN")")")" "$D" "$L"
  for try in 1 2; do
    ev assemble start "조립 시도 $try/2" "$D" "$L"
    if bash "$W/worship-assemble.sh" "$D" "$L" >/dev/null 2>&1 && $PY "$W/worship_verify.py" "$O" >/dev/null 2>&1; then
      ev verify ok "READY 생성" "$D" "$L"; READY+=("$L"); return 0
    fi
    ev verify fail "시도 $try/2 실패: $(tr -d '\n' < "$O/FAILED.json" 2>/dev/null | cut -c1-160)" "$D" "$L"
    [ "$try" = 1 ] && sleep "$RETRY_WAIT"
  done
  FAILED+=("$L"); return 1
}

if [ "$MODE" = deadline ]; then
  pre=0; for L in ko en; do [ -e "$B/output/${D}_$L/READY" ] || pre=1; done
  [ "$pre" = 1 ] && { ev deadline fail "09:20 아직 미완성" "$D"; tell "⏰ ${D} 예배가 09:20에 아직 미완성입니다. 조립이 가능하면 계속 진행하며, 안 되면 다른 창이 어제 영상을 '재방송'으로 내보냅니다."; }
fi
for L in ko en; do ensure "$L"; done

case "$MODE" in
  night)
    ev check ok "야간 점검 — 완성 ${READY[*]:-없음} · 대기 ${MISSING[*]:-없음} · 실패 ${FAILED[*]:-없음}" "$D"
    [ ${#FAILED[@]} -gt 0 ] && tell "❌ ${D} 예배 조립 실패(${FAILED[*]}). 05:30 점검이 다시 시도합니다. 사유: $B/output/${D}_${FAILED[0]}/FAILED.json" ;;
  check|deadline)
    ev "$MODE" ok "완성 ${READY[*]:-없음} · 묶음없음 ${MISSING[*]:-없음} · 실패 ${FAILED[*]:-없음}" "$D"
    if [ ${#MISSING[@]} -gt 0 ]; then
      tell "⚠️ ${D} 예배 낭독 묶음 없음(${MISSING[*]}) — 맥미니 확인: cat ~/Work/foreman/status.txt · 반장이 멈췄으면(연속 2회 실패) rm ~/Work/foreman/state/00-worship.fails · 수동: bash ~/Work/nexis-music/scripts/worship/worship-mac.sh ${D}"
    fi
    [ ${#FAILED[@]} -gt 0 ] && tell "❌ ${D} 예배 조립 실패(${FAILED[*]}). 사유: $B/output/${D}_${FAILED[0]}/FAILED.json"
    [ "$MODE" = deadline ] && [ ${#READY[@]} -eq 2 ] && tell "✅ ${D} 예배 한글·영어 완성(늦게라도 READY 생성)" ;;
esac
echo "===== $(date '+%F %T') 끝 — 완성 ${READY[*]:-없음} · 묶음없음 ${MISSING[*]:-없음} · 실패 ${FAILED[*]:-없음}"

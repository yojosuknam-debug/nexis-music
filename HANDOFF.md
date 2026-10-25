# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-10-25 09:20 · 동기부여(nexis-motiv) 내 목소리 쇼츠 — 시범·원고 은행·밤샘 91편·13편 다시 만들기 (데스크탑)
- 상태: 커밋 95f25b5(+ 이 HANDOFF) · 배포 해당 없음 · 업로드 **안 함**(사용자 지시) · 작업트리 깨끗
- 한 일:
  - `scripts/worship/motiv.py` — 원고 → 내 목소리(예배와 같은 B 목소리, Chatterbox) → 세로 1080×1920 쇼츠. `--bank`(원고 은행 연속 제작, `--until`·`--max`), `--redo`(지정 편만 다른 씨앗·5번 시도), 8편마다 다시 띄우기(`MOTIV_RESTART_EVERY`), 예배 작업(build_worship·simbang)이 돌면 대기.
  - `scripts/worship/motiv_check.py` 원고 검사기, `docs/motiv-bank.md` 형식·주제 지도, `data/motiv/2026-10-25_{a..d}.jsonl` 원고 100편(m0001~m0100, 검사 통과).
  - 밤샘(사용자 승인): 01:11~07:03 91편(m0001~m0091) 완성·실패 0 → 미니PC 외장하드 `/mnt/external/macmini/<이관 시각>/motiv/m00xx/`(mp4·script.json, 약 90MB).
  - 되읽기 오류 12% 넘은 13편을 `--redo`로 다시 만들어 미니PC로 보냄(script.json `"redo": true`).
- 레포 밖 변경:
  - 맥미니 `~/Work/nexis-motiv/` (레포 밖 실행본): `motiv.py` 사본(CRLF 제거 복사), `bank/`(원고 사본), `run-night.sh`·`run-redo.sh`, `output/done.txt`(91개)·`redone.txt`(13개), `logs/night-2026-10-25.log`·`redo-2026-10-25.log`. 자동 실행 등록(LaunchDaemon·크론)은 **없음**.
  - 결과 이관은 기존 `archive-outbox`(10분 주기)만 사용 — 미니PC 설정 변경 없음.
- 확인 못 한 것:
  - **편당 제작 시간이 갈수록 늘어남**(86초 → 404초, 다시 띄운 뒤에도 157 → 527초). 다시 띄우기는 원인 아님. 같은 시간 다른 GPU 작업·발열 경고 없음(01:15~08:30 맥에서 다른 음성 파일 생성 흔적 없음), 끝난 뒤 swap 1GB 사용 → 메모리 부족 의심, 미확인.
  - 다시 만든 13편 중 8편은 12% 언저리, m0085는 25%(원고 문장 "싫다는 말을 못 해 또 일을 떠안았습니다." 바꾸는 게 나을 수 있음). 사람이 들어 보지는 않음.
- 다음 할 일: 느려지는 원인 찾기 → 남은 9편(m0092~m0100) 제작 → 원고 품질 기준(보류 중) → 미니PC 예약 업로드(승인 후).
- 주의:
  - nexis-qt 채널은 실시간 예배 전용 — motiv 영상을 거기 올리지 않는다.
  - 미니PC에 옛 13편 사본이 이전 이관 폴더에 남아 있음(지우려면 승인 필요). 업로드 시 `"redo": true` 쪽 사용.
  - 맥 실행본을 바꿀 땐 `tr -d '\r'`로 복사(맥 레포 `~/Work/nexis-music` 안에 넣으면 git pull 충돌).

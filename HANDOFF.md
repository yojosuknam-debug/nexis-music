# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-10-26 19:40 · 동기부여 쇼츠 — 첫 자동 업로드 확인·실패 텔레그램 알림·채널 설명 '매일 아침' (데스크탑)
- 상태: 이 커밋(motiv_publish.py 알림 + 이 HANDOFF) · 배포 = 미니PC `~/bin/motiv_publish.py` 교체(레포와 같음, LF) · 작업트리 깨끗
- 한 일:
  - 10-26 07:40 크론 첫 자동 업로드 **성공** — m0086 https://youtu.be/IoTs0RYTcuI (AI 합성 표시 ok). 남은 97편, 다음 m0056.
  - `motiv_publish.py` 텔레그램 알림: 업로드 실패(원인 한 줄)·예상 못 한 오류(영상 없음·시간 초과 등)·남은 편 ≤7(`LOW`)·모두 올림. 토큰은 `~/autovid/.env.local` 에서만 읽어 POST(argv·로그 노출 없음, cron_guard 와 같은 방식). 시험 알림 1통 보냄(보내기 오류 없음).
  - 유튜브 채널 설명 "매주 올립니다" → "매일 아침 올립니다"(API brandingSettings, 키워드 그대로). 반영 확인.
- 레포 밖 변경: 미니PC `~/bin/motiv_publish.py` 교체, 이전본 `~/bin/motiv_publish.py.bak-20261026`(비밀값 없음). crontab·docker·터널은 안 건드림.
- 확인 못 한 것: 시험 알림이 실제 텔레그램에 도착했는지(사용자 확인 필요) · 실패 알림은 실제 실패 상황에서 아직 안 울려 봄 · m0085·m0099 발음.
- 다음 할 일: 원고 더 쓰기(원고 품질 기준 먼저 정하기 → m0101~ 원고+hooks → 맥미니 제작 → `motiv_collect.py`). 남은 97편이라 급하지 않음(알림이 7편 남으면 알려 줌).
- 주의: `올린기록.csv` 지우지 말 것. 미니PC 설정 변경은 사용자 승인 후.

## 2026-10-25 19:40 · 동기부여 쇼츠 — 배경 그림·100편 완성·미니PC 정리·유튜브 매일 자동 업로드 시작 (데스크탑)
- 상태: 커밋 abedb70(+ 이 HANDOFF) · 배포 = 미니PC `~/bin` 사본·맥 `~/Work/nexis-motiv` 사본(레포와 같음) · **업로드 시작함**(사용자 지시) · 작업트리 깨끗
- 한 일:
  - 배경: Higgsfield 그림 20장(주제 10 × 장면·미소녀풍) + '시작' 주제 반복 영상 2개(20크레딧, 잔액 37.6). 장면·미소녀풍을 편 번호로 번갈아(사용자 확정). `motiv.py` 배경 합성·`--compare` 비교본.
  - 남은 9편(m0092~m0100) 배경 넣어 제작 → 100편 완성. m0001~m0091 은 단색 화면(사용자: 둘 다 좋다, 그대로 씀).
  - 미니PC `/mnt/external/nexis-motiv/`(영상 100·원고 100·이전본 13·목록.md/csv) 로 정리 — `motiv_collect.py`.
  - 유튜브: 첫 편 m0017 https://youtu.be/sQmn6T-LWpc ('하루 한 줄, 동기부여', 공개, AI 합성 표시). 매일 07:40 한 편 자동 — `motiv_publish.py`(무작위 순서·중복 없음), 제목·첫 문장 100편 `data/motiv/hooks.jsonl` + `motiv_meta.py`.
- 레포 밖 변경:
  - **미니PC crontab 한 줄 추가** `40 7 * * * /usr/bin/python3 ~/bin/motiv_publish.py >> /mnt/external/nexis-motiv/업로드/upload.log` (백업 `~/crontab-backup-2026-10-25-motiv.txt`). `~/bin/motiv_collect.py`·`motiv_publish.py` 사본. docker·compose·터널은 안 건드림(autovid-bot 을 exec 로만 씀).
  - 미니PC `/mnt/external/nexis-motiv/업로드/`(순서.txt·올린기록.csv·메타/100개), 임시 복사 폴더 `/mnt/external/autovid/output/motiv-upload/`(올린 뒤 비움).
  - 맥미니 `~/Work/nexis-motiv/bg/`(그림 20·반복 영상 2), `run-bank.sh`. 원본 그림 데스크탑 `D:\YH\output\motiv-bg`.
- 확인 못 한 것: 내일 07:40 첫 자동 업로드(크론으로 실제 도는지) · 업로드 실패 알림 없음(로그만) · 채널 설명이 아직 "매주 올립니다" · m0085·m0099 발음(사람이 안 들어 봄) · 새 영상 생기면 `motiv_collect.py` 를 손으로 돌려야 순서에 들어감.
- 다음 할 일: 내일 upload.log·올린기록.csv 확인 → 실패 알림(텔레그램) 붙이기 → 채널 설명 '매일'로 → 원고 더 쓰기(hooks 도 함께).
- 주의: 100편이면 약 100일치. 같은 편 다시 올리지 않게 `올린기록.csv` 지우지 말 것. 미니PC 설정 변경은 사용자 승인 후.

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

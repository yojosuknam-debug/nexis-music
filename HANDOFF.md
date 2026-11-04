# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-04 22:50 · 실시간 예배 — 원곡·따라 부르기 안내·주기도문 싱크 수정, 매일 제작 도구 작성(크론 미등록) (데스크탑)
- 상태: 커밋 44812af·d035bcb·(주기도문 qc)·(매일 제작 도구)·(verify 쉼표) 모두 push · 11-05 한·영 영상 수정판 텔레그램 전송(수정 전 영상은 폐기) · **미니PC 크론 미등록, 맥 반장 일감은 꺼짐 상태**
- 한 일:
  - 함께 찬송·응답 찬양 = 보컬 원곡 그대로(`sing_along` 제거), 기도회 배경만 연주곡. 가사 있는 찬양 앞 안내 문장(`SING_CUE`: 따라 부르기·마음속으로 음미)을 예배의 부름·결단 기도 끝에 붙임(영어판은 번역 때 한국어 안내를 빼고 영어 안내를 따로 붙임).
  - 주기도문·축복 저장 음성(cache)에 문장 시간표가 없어 자막이 뒤로 갈수록 어긋나던 것 → `cache_*.qc.json` 사이드카 저장·재사용. 영상 총 길이=음성 길이+대기 300초 일치 확인(귀로는 미확인).
  - 매일 제작 도구(미니PC): `worship_verify.py`(완성 판정·READY/FAILED.json·H.264 1080p30·AAC 48kHz·키프레임≤4초·길이±3초) · `worship_ops.py`(schedule.jsonl 로그·텔레그램, 토큰은 ~/autovid/.env.local 에서만) · `worship-nightly.sh`(기본=내일분/--check/--deadline/--date/--verify-only/--no-notify) · `render_video.py` 음성 48kHz 추가.
  - 맥 반장 일감 `00-worship.sh`(book-summary-video/mac/foreman/jobs.d 원본 로컬 커밋만—원격 없음, 맥 ~/Work/foreman/jobs.d 에 복사). **`state/worship.enabled` 파일이 있어야 동작**(지금 없음=꺼짐).
- 실측: 맥미니 낭독 한·영 합쳐 91분(10:01→11:32, 원고 생성 포함), 조립 편당 약 8분. 맥 낭독 21:30 시작 → 약 23:05 → 이관 ≤10분 → 미니PC 조립 시작은 23:40 권장.
- 시험 중: 22:39 `worship-nightly.sh --date 2026-11-05 --no-notify` 를 미니PC 에 띄움(11-05 를 48kHz 로 다시 조립 → READY). **결과 확인 못 함**: `/mnt/external/nexis-worship/logs/nightly-2026-11-05.log`·`schedule.jsonl`·`output/2026-11-05_*/READY`. 시험 전 판정은 두 영상 모두 음성 44.1kHz 한 가지만 불합격(길이·키프레임 2초 통과).
- 다음 할 일(승인 조건 그대로): ① 시험 통과 확인·보고 → ② 미니PC 크론 3줄 등록(`40 23`·`30 5 --check`·`20 9 --deadline`, 각 flock, 등록 전 `crontab -l > ~/crontab.bak-날짜`) → ③ 맥 `touch ~/Work/foreman/state/worship.enabled`(11-05분은 `state/worship-2026-11-05.done` 먼저 만들어 중복 방지) → ④ 매일 제작 안내(영상 위치·이름 규칙·길이·형식)를 다른 창에 전달. 방송 송출·토큰·`worship-stream.sh` 는 다른 창 몫(건드리지 않음). 09:20 미완성 시 다른 창이 '재방송' 처리(READY 안 만듦).
- 레포 밖 변경: 맥미니 `~/Work/foreman/jobs.d/00-worship.sh`(꺼짐) · 미니PC `/mnt/external/nexis-worship/output/2026-11-05_*` 재조립 중 · 맥 `script.json.bak-cue` 백업 · 미니PC 외장 `macmini/2026-11-04_*` 묶음 여러 개.
- 확인 못 한 것: 영상을 귀로 들어 보지 않음(싱크·영어 축복 인식 오류 56%) · 한국어 축복 자막 합이 음성보다 3.7초 짧게 나옴(계산 방식 탓인지 미확인) · 현황판 일정 탭의 로그 형식(schedule.jsonl 은 제안안).
- 주의: 이 PC 의 미커밋 docs/research 4개는 다른 창 것(커밋 안 함). 맥에서 `nohup … &` 로 띄우면 로그 없이 안 돌았음 → 직접 실행.

## 2026-11-04 13:30 · 실시간 예배 11-05 — 맥 목소리 묶음 실패 고침·미니PC 조립 완료 (맥미니)
- 상태: 이 커밋(build_worship.py 한 줄 + 이 HANDOFF) · 맥·미니PC 둘 다 이 커밋 전 a5a17d0 으로 실행 · 방송 예약 **안 함**(SCHEDULE=0)
- 한 일:
  - 아침 10:01 `worship-mac.sh 2026-11-05` 이 ko·en 둘 다 `lords_prayer: 목소리 파일이 없다` 로 묶음 실패. 원인: `make_voice` 가 주기도문·축복 **저장본(cache/)을 쓰면 script.json 을 안 쓰고 continue** → 맨 끝 두 순서의 audio 가 저장 안 됨. 저장본 사용 때도 script.json 쓰도록 수정.
  - 맥 다시 실행(문장 저장본 재사용, 1분) → 묶음 ko·en → 미니PC 이관 확인 → 미니PC `worship-assemble.sh 2026-11-05` 손으로 실행(16분).
  - 결과: `/mnt/external/nexis-worship/output/2026-11-05_ko/worship_2026-11-05_ko.mp4`(20:30) · `…_en/worship_2026-11-05_en.mp4`(22:49), mp3 함께.
- 레포 밖 변경: 미니PC 외장하드 `macmini/2026-11-04_105200`·`_114206` 에 실패 때 남은 **반쪽 묶음**(bundle.json 없음 → find 가 무시) — 지우려면 승인 필요.
  - 오류 높은 문장 다시 받아쓰기 확인: ko 설교 2문장이 **중간에 끊김**("…시인은"까지 2.2초, "…다시 살게 하고"까지 3.5초). 씨앗이 1000~1002 고정이라 그냥 다시 돌리면 같은 결과 → 씨앗 2000번대로 두 문장만 다시 만듦(62%→3%, 42%→3%, 원본은 `_chunks_bak/`) → ko 다시 묶기·조립(14:29, 20:35). en 3문장은 원고대로 읽힘('Wilt thou' 옛 영어라 오류율만 높음).
- 확인 못 한 것: 사람이 전체를 안 들어 봄.
- 텔레그램 전송: 받는 봇은 **@Nexis_file_bot**(미니PC 로컬 Bot API 서버 `telegram-bot-api` 컨테이너, 2GB). 이번엔 실수로 옛 @nexis_autovid_bot(api.telegram.org, 50MB 제한)으로 원본을 보내 봤고 결과 확인 못 함(아마 실패) → 사용자 "나중에". 720p 미리보기판(40·41MB)은 맥 스크래치에만 있음(세션 끝나면 사라짐).
- 다음 할 일: 11-05 영상 2개를 @Nexis_file_bot 으로 보내기(chat_id·로컬 서버 주소는 미니PC `~/telegram-bot-api/` 설정에서 확인, 값 출력 금지) · 방송 예약(SCHEDULE=1)·송출은 사용자 결정. 개선 후보: `say()` 가 길이로 끊김을 못 잡음(오류율만 봄) — 원고 길이 대비 너무 짧으면 다른 씨앗으로 더 시도.
- 주의: `voice_bundle.py pack` 은 실패해도 반쪽 폴더를 outbox 에 남긴다(이관됨).

## 2026-10-26 19:40 · 동기부여 쇼츠 — 첫 자동 업로드 확인·실패 텔레그램 알림·채널 설명 '매일 아침' (데스크탑)
- 상태: 이 커밋(motiv_publish.py 알림 + 이 HANDOFF) · 배포 = 미니PC `~/bin/motiv_publish.py` 교체(레포와 같음, LF) · 작업트리 깨끗
- 한 일:
  - 10-26 07:40 크론 첫 자동 업로드 **성공** — m0086 https://youtu.be/IoTs0RYTcuI (AI 합성 표시 ok). 남은 97편, 다음 m0056.
  - `motiv_publish.py` 텔레그램 알림: 업로드 실패(원인 한 줄)·예상 못 한 오류(영상 없음·시간 초과 등)·남은 편 ≤7(`LOW`)·모두 올림. 토큰은 `~/autovid/.env.local` 에서만 읽어 POST(argv·로그 노출 없음, cron_guard 와 같은 방식). 시험 알림 1통 보냄(보내기 오류 없음).
  - 유튜브 채널 설명 "매주 올립니다" → "매일 아침 올립니다"(API brandingSettings, 키워드 그대로). 반영 확인.
- 레포 밖 변경: 미니PC `~/bin/motiv_publish.py` 교체, 이전본 `~/bin/motiv_publish.py.bak-20261026`(비밀값 없음). crontab·docker·터널은 안 건드림.
- 확인 못 한 것: (시험 알림 텔레그램 도착은 사용자 확인 완료) · 실패 알림은 실제 실패 상황에서 아직 안 울려 봄 · m0085·m0099 발음.
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

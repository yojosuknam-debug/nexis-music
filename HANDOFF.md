# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-05 23:35 · end — 온라인 예배 시험 방송 성공 확인 (DESKTOP-8ISD10M)
- 상태: 확인만 함(코드 변경 없음) · 이 HANDOFF 커밋만
- 한 일: 미니PC `logs/schedule.jsonl` 확인 — 11-05 23:05:08 시험 방송 시작 → 23:09:42 `ok`(다시보기 비공개), https://youtu.be/7vqT1tKntKI (한국어 180초). 텔레그램 성공 알림도 사용자 수신.
- 레포 밖 변경: 없음. 크론의 시험 줄(`5 23 5 11 … # nexis-worship-onair-test`)은 **아직 남아 있음**(2026년 11-05만 돌게 돼 있어 다시 울리진 않음) — 지우기는 사용자 승인 대기.
- 확인 못 한 것: 영상·소리 실제 상태(스튜디오에서 사람 확인) · 재생목록 추가(시험은 keep=false라 안 돎 → 11-06 10시 ko·13시 en이 첫 실행) · 23:29 기준 `output/2026-11-06_*` 아직 없음(23:40 조립 예정이라 정상 범위).
- 다음 할 일: 11-06 05:30 check·09:20 deadline 알림으로 11-06 영상 READY 확인 → 10:00 첫 방송·재생목록 확인 → 시험 크론 줄 삭제(승인 후, 백업 남기고).
- 주의: 미커밋 `docs/research/*`는 이 창 것 아님.

## 2026-11-04 23:40 · end — 온라인 예배 하루 8회 송출 등록 (DESKTOP-8ISD10M)
- 상태: 이 메모와 함께 커밋·push · 미니PC `git pull` 반영(`scripts/worship/worship_onair.py`, `worship-onair.sh`) · 크론 등록됨 · 실제 방송은 아직 0회
- 한 일: 예배 5분 전 크론이 방송 생성→재인코딩 없이 송출→다시보기 정리. 한 10·16·22·04 / 영 13·19·01·07. D일 영상은 D일 10시~다음 날 07시. READY 없으면 어제 영상 '재방송'+알림, 그것도 없으면 건너뜀+알림. 10시 ko·13시 en만 공개 보관+재생목록, 나머지 6회는 끝나면 비공개. 11-06 09:30 전엔 안 돔(FIRST_ON_AIR)
- 레포 밖 변경: 미니PC 크론 `55 3,9,15,21`(ko)·`55 0,6,12,18`(en)·시험 1회 `5 23 5 11`(백업 `~/crontab.bak-onair-20261105`) · `/mnt/external/nexis-worship/.youtube_token_live.pickle`(600) · 예배 `.venv`에 구글 라이브러리 설치
- 채널: '매일 온라인 예배' @online-worship-24(UCfc-DVXcjjFii_nhSdeORWQ). 라이브는 11-05 22:44쯤 켜짐(유튜브 카운트다운 기준)
- 확인 못 한 것: 실제 라이브 송출 전체(11-05 23:05 비공개 180초 시험이 첫 확인, 결과 텔레그램) · 다시보기 비공개·재생목록 처리 · 할당량
- 다음 할 일: 시험 성공 확인 후 크론의 `nexis-worship-onair-test` 줄 삭제 · 11-06 10:00 첫 방송 확인 · 채널에 '예정' 미리 띄우기(현재 5분 전 생성)는 안정 뒤 검토
- 주의: `worship-stream.sh`는 옛 방식이라 쓰지 않음. 비밀값 없는 일정 로그 `logs/schedule.jsonl`(stage=onair). 미커밋 `docs/research/*`는 이 창 것 아님

## 2026-11-04 22:50 · 실시간 예배 — 원곡·따라 부르기 안내·주기도문 싱크 수정, 매일 제작 도구 작성(크론 미등록) (데스크탑)
- 상태: 커밋 44812af·d035bcb·(주기도문 qc)·(매일 제작 도구)·(verify 쉼표) 모두 push · 11-05 한·영 영상 수정판 텔레그램 전송(수정 전 영상은 폐기) · 크론 3줄 등록·맥 반장 일감 켬(11-04 23:07)
- 한 일:
  - 함께 찬송·응답 찬양 = 보컬 원곡 그대로(`sing_along` 제거), 기도회 배경만 연주곡. 가사 있는 찬양 앞 안내 문장(`SING_CUE`: 따라 부르기·마음속으로 음미)을 예배의 부름·결단 기도 끝에 붙임(영어판은 번역 때 한국어 안내를 빼고 영어 안내를 따로 붙임).
  - 주기도문·축복 저장 음성(cache)에 문장 시간표가 없어 자막이 뒤로 갈수록 어긋나던 것 → `cache_*.qc.json` 사이드카 저장·재사용. 영상 총 길이=음성 길이+대기 300초 일치 확인(귀로는 미확인).
  - 매일 제작 도구(미니PC): `worship_verify.py`(완성 판정·READY/FAILED.json·H.264 1080p30·AAC 48kHz·키프레임≤4초·길이±3초) · `worship_ops.py`(schedule.jsonl 로그·텔레그램, 토큰은 ~/autovid/.env.local 에서만) · `worship-nightly.sh`(기본=내일분/--check/--deadline/--date/--verify-only/--no-notify) · `render_video.py` 음성 48kHz 추가.
  - 맥 반장 일감 `00-worship.sh`(book-summary-video/mac/foreman/jobs.d 원본 로컬 커밋만—원격 없음, 맥 ~/Work/foreman/jobs.d 에 복사). **`state/worship.enabled` 파일이 있어야 동작**(지금 없음=꺼짐).
- 실측: 맥미니 낭독 한·영 합쳐 91분(10:01→11:32, 원고 생성 포함), 조립 편당 약 8분. 맥 낭독 21:30 시작 → 약 23:05 → 이관 ≤10분 → 미니PC 조립 시작은 23:40 권장.
- 시험 통과(11-04 22:58): 11-05 한·영 모두 새 기준으로 다시 조립 → READY(ko 63MB·en 73.4MB, 길이 오차 ≤0.3초, 키프레임 2초, AAC 48kHz). 실패 시험(묶음 없음·가짜 묶음 조립 실패)·텔레그램 알림 수신 사용자 확인.
- **등록 완료(11-04 23:07, 사용자 승인)**: 미니PC 크론 3줄(`40 23` 야간 · `30 5 --check` · `20 9 --deadline`, 각 flock, 주석 nexis-worship-nightly/check/deadline) · 백업 `~/crontab.bak-20261104`(되돌리기: `crontab ~/crontab.bak-20261104`) · 맥 `state/worship.enabled` 켬 + `worship-2026-11-05.done`(중복 방지). 끄기: 맥 `rm ~/Work/foreman/state/worship.enabled`.
- 다음: 11-05 21:30 부터 11-06 영상 첫 실전 제작(낭독 약 91분 → 23:15 이관 → 23:40 조립 → 약 23:57 READY 예정). 11-06 05:30 `schedule.jsonl`·`nightly-2026-11-06.log` 로 결과 확인. 방송 송출·토큰·worship-stream.sh 는 다른 창 몫.
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

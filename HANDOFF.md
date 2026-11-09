# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-09 23:40 · end — 음악 사이트 자동 배포·앨범 자동 발행·표지 104개 교체 (DESKTOP-8ISD10M)
- 상태: 커밋 aadaade(자동화)·b3ff456(앨범 12개)·ce43eda(표지 코드)·f3b3cfb(표지 104개) push·배포 확인 · 사이트 142앨범 1,027곡, 유튜브 목록 511건
- 한 일: Vercel GitHub 연동 끊김으로 사이트가 10-18에 멈춰 있던 것을 `deploy.yml`(토큰 방식, 라이브 data.js 대조)로 대체. `update-music-data.yml`은 데이터 변경 시 deploy.yml 호출. `auto_publish.py`+`release_gate.py`로 유튜브에 공개된 새 앨범만 자동 발행. `sync_project_covers.py`가 유튜브 표지를 같은 input 폴더의 프로젝트 thumbnail.png로 교체(쇼츠·오매칭 표지 104개 해소).
- 레포 밖 변경: GitHub Secrets VERCEL_TOKEN·VERCEL_ORG_ID·VERCEL_PROJECT_ID 추가 · 미니PC 크론 `30 18 * * *` `# nexis-jukebox-auto`(백업 `~/crontab.bak-jukebox-20261109-2207`, 로그 `~/jukebox-auto.log`) · 미니PC 레포 최신 pull · R2 음원·표지 업로드.
- 확인 못 한 것: 매일 유튜브 목록 갱신→deploy.yml 호출(첫 실전 11-10 오후, 그날 새 영상이 있어야 돎) · 11-10 18:30 크론 자동 실행 · 새 앨범 음원을 귀로 듣는 확인.
- 다음 할 일: 11-10 저녁 `gh run list`와 미니PC `~/jukebox-auto.log` 확인. 미조치: GUDI_SONG2 페이지 주소가 발행 때 바뀌는 문제(제목이 '굳이 이걸 노래로'·'굳이 이게 명곡이야'로 번갈아 잡힘).
- 주의: `/jukebox`·`run_all.py`를 손으로 돌리면 유튜브 공개 여부와 상관없이 폴더 전체를 발행(유튜브 필터는 자동 실행만). 표지 되돌리기 = f3b3cfb revert. 미커밋 `docs/research/*`는 이 창 것 아님.

## 2026-11-07 00:40 · end — 예배 채널에 예배 찬송 곡별 업로드(가사·해설) (DESKTOP-8ISD10M)
- 상태: 이 커밋(`scripts/worship/hymn_upload.py` 신규 + 이 메모) · 미니PC 실행본은 `/mnt/external/nexis-worship/hymn_upload.py`(레포와 같은 내용, scp 복사)
- 한 일: 예배에서 실제로 쓴 10곡(보컬 6 + 기도 연주 4: 1집·Daily Walk 각 2·4·5·6·8번)을 '매일 온라인 예배' 채널에 공개 업로드. 영상 = Still Waters 업로드 때 만든 `/mnt/external/suno-playlist/output/<앨범>_project/tracks_mp4/track_NN.mp4`(mp3와 길이 대조 OK). 설명 = 가사 전 절 + 곡 해설(album.md Track Notes 기준) + 방송 시간표 + AI 제작 표기. 재생목록 '예배 찬송 · 가사'·'Worship Hymns with Lyrics' 새로 만듦. 채널에 기존 찬송 영상 없음 → 중복 0.
  - 11-07 00:20 2곡 올림: 마르지 않는 샘 https://youtu.be/Cc4u6xBvmZw · As Watchmen Wait for Morning https://youtu.be/NyPFIZWsJmE (public 확인)
- 레포 밖 변경: 미니PC `/mnt/external/nexis-worship/hymn_upload.py`·`hymn_uploads_state.json`(올린 곡 기록)·`hymn_upload_loop.sh`(nohup 백그라운드, 매일 16:25 최대 5곡, 다 올리면 종료, 최대 7일) · 로그 `logs/hymn_upload.log`. 크론·컨테이너 안 건드림.
- 할당량: 예배 토큰 = autovid GCP 프로젝트(16채널 공유), 업로드 1곡≈1,650유닛 → 송출 보호 위해 16:25(초기화 17:00 직전, 방송 없는 시간)에만 올림.
- 확인 못 한 것: 남은 8곡 실제 업로드(11-07 16:25 5곡, 11-08 16:25 3곡 예정 — 텔레그램 알림) · containsSyntheticMedia 값이 조회 응답에 안 나옴(설명엔 AI 표기 있음) · 영상 처리 완료 후 화면·소리.
- 다음 할 일: 텔레그램 알림 확인. 미니PC 재부팅되면 루프가 죽음 → `nohup setsid /mnt/external/nexis-worship/hymn_upload_loop.sh &` 다시(이미 올린 곡은 건너뜀). 새 찬송이 예배에 쓰이면 `SONGS`에 추가.
- 주의: 미커밋 `docs/research/*`는 이 창 것 아님.

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

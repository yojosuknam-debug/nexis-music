# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-11 22:15 · end — Suno 곡 멜론 유통 준비: 마스터링·유통사 조사 (DESKTOP-8ISD10M)
- 상태: 조사 문서 커밋·push(e4b1990 + 이번 커밋) · 문서만이라 사이트 변화 없음(push 시 Actions 배포는 돎)
- 한 일: `/px` 조사 3건 — `docs/research/2026-11-11_suno-마스터링-에이전트.md`(규격 -14 LUFS·-1 dBTP·16bit/44.1k, 내 Suno 실측) · `2026-11-11_멜론-유통사-선정.md`(교차, 원문 `_퍼플렉시티.md`) · 10-27 유통 조사 미커밋분 함께 커밋. 마스터링 도구는 별도 레포 `D:\YH\APP\suno-master`(/master).
- 결론: 루트노트=한국 스토어 AI곡 거절(공식) / 튠코어=Suno v6 곡만, 한국 승인 사례 없음 / **국내 후보: 뮤즈플랫폼(조선힙합 Suno곡 멜론 실발매, BASIC 무료·20%)·흐름 HREUM(Suno 공동창작 검수, 국내 수수료 0%, 등록비·계약조건 미공개, 2026-10 출범)·KGMUSIC(개인·Suno 입력 안내, 3.9~9.9만원, 승인 후 반려 환불 없음)·OGQ 블렌딩(머무르 실발매)** · 지니릴리 2026-06-30 종료.
- 사용자 결정: **비용 없이 개인이 접근 가능하면 흐름(HREUM)으로 멜론 등록**하고 싶음.
- 확인 못 한 것: 흐름의 등록비·옵션비 0원 여부, 계약 기간·독점·권리 조항, 해외 맞춤 조건 · 머무르/조선힙합 발매사(퍼플렉시티 확인만, 멜론·벅스 직접 열람 실패)
- 다음 할 일: 흐름 문의(hreum.kr 문의 양식, 'AI 활용 정도' 칸 있음) — 비용 0원 여부·계약 기간·독점·권리·국내만 위탁 가능 여부·정산 주기 서면 확인. 데모 1곡 `/master`로 준비. 답이 나쁘면 뮤즈플랫폼 BASIC.
- 주의: Suno 상업 이용은 유료 플랜 다운로드만. 기존 album-drafts는 v4.5~v5(튠코어는 불가, 국내는 버전 언급 없음).

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

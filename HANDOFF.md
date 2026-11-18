# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-18 · end — Vercel 배포 저장공간 절약: .vercelignore 신설 (DESKTOP-8ISD10M)
- 상태: e594019(`.vercelignore` 신규) push · 배포는 안 돌았음(deploy.yml paths 필터에 .vercelignore 없음) → 다음 app/public 변경 배포 때 자동 적용. 화면 변화 없는 변경이라 강제 배포 안 함
- 한 일: Vercel 무료 팀 배포 저장공간 10GB 도달 메일 대응. music 배포에 사이트가 안 쓰는 `scripts/`·`output/`·`docs/`·`.github/`·`*.md` 제외(배포 1회 약 40MB 절감). app 코드·next.config가 이 폴더를 참조 안 함 확인.
- 주의: 앞으로 app 코드가 scripts/ 등을 import 하면 `.vercelignore`에서 빼야 빌드가 깨지지 않음.

## 2026-11-15 · end — 헌금송 1·2집 주크박스·예배 대장 반영 + /px 헌금송 조사 (DESKTOP-8ISD10M)
- 상태: 커밋 21bd3ee(주크박스, 데스크탑 `run_all.py --no-push` 후 수동 커밋)·49682d8(music.json)·이번 커밋(조사 문서) push · Vercel 배포 → radio.json에 헌금송 반영 확인
- 한 일: `/px` 조사 `docs/research/2026-11-15_헌금송-성가대특송-작법.md`. youtube-playlist 헌금송 1·2집(stillwaters, 15곡) 업로드 후 주크박스 반영. `music_library.py sync` → 35곡 신규(밀려 있던 아침 찬송 3집·Daily Walk 3집 20곡 + 헌금송 15곡). **헌금송 15곡은 license.status=hold**(예배 선곡 제외, 사용자 결정 — 온라인 예배엔 헌금 순서 없음). 14일×한·영 pick_songs 모의에서 헌금송 0회.
- 🔴 확인 필요(내 실수): 데스크탑 run_all이 GUDI_SONG을 데스크탑 사본으로 다시 읽어서 21bd3ee에서 **「굳이 이걸 노래로」 앨범이 빠지고 「굳이 이게 명곡이야?」(GUDI_SONG2, 음원 중복 7곡)가 추가됨**. 바로잡기 = 미니PC에서 `cd /mnt/external/nexis-music && JUKEBOX_RELEASED_ONLY=1 ~/suno-venv/bin/python -c "import sys;sys.path.insert(0,'scripts/jukebox');import bot_command;bot_command._work(print)"` (자동 권한에서 막혀 미실행 — 사용자 결정 대기).
- 주의: 발행은 미니PC에서만(데스크탑 run_all 금지 — 이번에 재발). run_all은 `git add -A`라 미커밋 문서까지 섞으니 `--no-push` 후 골라 커밋.

## 2026-11-12 23:10 · end — 옛 앨범 8개 주크박스·라디오 합류 + 곡제목 파싱 수정 (DESKTOP-8ISD10M)
- 상태: 커밋 2c8f368·4b6987d·7e7d864 push · 미니PC 레포 pull 완료 · 발행은 미니PC `JUKEBOX_RELEASED_ONLY=1 bot_command._work` 로 실행 → Actions(Deploy to Vercel) 배포 · 라이브 156앨범·1133곡 확인(페이지·음원 9개 206, 라디오 22:50 '156앨범' 로드)
- 한 일: 11-12 새벽 6앨범(TWO_NOTCHES_WARMER 등) 자동 발행·라디오 반영 점검(정상). 4~6월 앨범 8개(GRAY_WINDOW·LANGUAGE_OF_RAIN·RAIN_ON_THE_EAVES·small_joys_cafe·sonjeorilgi·mot_ij_eo·neon_echoes·Moonflow Night, 64곡)가 유튜브엔 있는데 0곡 파싱으로 빠져 있던 것 수정 — `scripts/jukebox/scan_albums.py`: mp3 `track01`/`Track 1_` 인식, `## 🎵 Track 01:` 이모지 제목, album 없는 설명 md 대체, 제목 앞 대시 제거, `### Title` 코드펜스 제목(SILK_VILLAGE·weightless 표시도 고쳐짐).
- 확인 못 한 것: GUDI_SONG 은 데스크탑 input 사본이 미니PC와 달라 데스크탑 run_all 시 곡목록이 바뀜(기존 미결) — 발행은 미니PC에서만.
- 다음 할 일: 없음. (auto_publish 는 '처음 보는 앨범'만 발행 — 카탈로그에 0곡으로 있던 앨범은 수동 RELEASED_ONLY 실행 필요, 메모리 nexis-music-jukebox-status)
- 주의: 수동 /jukebox·run_all 은 유튜브 미공개 앨범도 발행함(Between Two Midnights 가 그렇게 먼저 공개돼 있었음).

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

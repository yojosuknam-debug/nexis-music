# HANDOFF — 창 인계 기록 (최근 5개, 새 항목이 맨 위)

## 2026-11-22 21:55 · end — 11-22 배치 6앨범 반영·곡별 영상 대기 확인(점검만, 코드 변경 없음) (DESKTOP-8ISD10M)
- 상태: 코드 변경 없음 · 이 HANDOFF 커밋만 · 배포 불필요
- 한 일: 6앨범(COAT_POCKETS·FEAR_NOT·TEA_ROOM_DAY·LEGENDS_SUNG_ANYWAY·THIRTY_MINUTES_BEFORE·KEEPERS_HOURS) 텔레그램 /jukebox 발행(f079504) 확인 → 라이브 radio.json 173앨범·1274곡, 6앨범 페이지·표지·첫/끝 곡 음원 200, 미니PC 레포 f079504. 미니PC hymn_upload_loop2.sh 실행 중(11-23 16:25까지 sleep), dry-run = 1집 10곡 done · 30곡 todo(mp4·설명문 모두 있음), 하루 5곡 → 11-28경 완료.
- 확인 못 한 것: 곡별 영상 2차 첫 업로드(11-23 16:25) 결과.
- 다음 할 일: 11-23 저녁 미니PC `/mnt/external/nexis-worship/logs/hymn_upload.log`에 "(2차)" 5곡(ko1-03·en1-03·ko1-01·en1-01·ko1-09) 확인. 성탄 찬송 앨범 건은 아래 항목 그대로.
- 주의: 데스크탑 Git Bash `ssh minipc`는 publickey 거부 → PowerShell `C:\Windows\System32\OpenSSH\ssh.exe minipc` 사용. 원격 명령에 큰따옴표+파이프 섞으면 따옴표가 깨져 명령이 멈춤.

## 2026-11-22 · end — 라디오·주크박스·예배 최신 곡 점검 + 예배 곡별 영상 30곡 준비 + 성탄 절기 선곡 (DESKTOP-8ISD10M)
- 상태: d14db16(music.json sync)·e9e0e9d(hymn_upload 여러 앨범·hymn_songs.json 30곡·music_library 절기) push · 사이트 변화 없는 scripts 변경이라 배포 불필요 · 미니PC 레포 pull 완료(e9e0e9d)
- 한 일: 사이트·라디오 167앨범·1226곡 일치 확인(누락=오늘 16:15 배치 6앨범 COAT_POCKETS·FEAR_NOT·TEA_ROOM_DAY·LEGENDS_SUNG_ANYWAY·THIRTY_MINUTES_BEFORE·KEEPERS_HOURS, 유튜브 업로드 중). 예배 대장 sync → 새 찬송 없음, 크리스마스 합창 Every Voice Tonight 8곡(ccm) 추가·선곡 0회 확인. 예배 곡별 영상: 11월 예배에서 실제 부른 1집 나머지 5·2집 6·3집 4 × 한·영 = 30곡 설명문(`scripts/worship/hymn_songs.json`, 개역한글·KJV 인용 대조 수정) + hymn_upload.py ALBUMS 표(1집 10곡 키·제목 동일 확인). 절기: music.json `season: christmas`(sync가 앨범 제목 성탄/대림/Christmas/Advent+찬송이면 자동) → 대림절 첫 주일(2026-11-29)~1/5에만, 기간 중 여는 찬송·기도회 배경 우선(모의 확인).
- 레포 밖 변경: 미니PC `/mnt/external/nexis-worship/hymn_upload_loop2.sh`(레포 최신본 실행, 매일 16:25 5곡, 11-23~ 약 6일, 로그 `logs/hymn_upload.log`, 백그라운드 실행 중) · 데스크탑 대기 작업(배치 끝나면 Update Music Data 수동 실행 → 미니PC auto_publish → 확인, 이 창 종료 시 함께 꺼질 수 있음) · 메모리 radio-worship-plan·hymn-albums-2026 갱신.
- 확인 못 한 것: 오늘 배치 6앨범 주크박스·라디오 반영(대기 작업이 못 끝내면 → 내일 Update Music Data 후 18:30 auto_publish가 자동 발행) · 곡별 영상 첫 업로드(11-23 16:25) 결과.
- 다음 할 일: 11-23 저녁 radio.json에 6앨범 있는지·`logs/hymn_upload.log` 5곡 확인. 성탄 찬송 앨범(youtube-playlist album-drafts/CHRISTMAS_HYMNS_KO·EN) mp3 업로드되면 주크박스 반영 → `music_library.py sync`(season 자동) → hymn_songs.json에 곡별 영상 추가.
- 주의: 곡별 영상 새 곡 = hymn_songs.json 항목 추가(1집 처음 10곡 키 ko02 등은 바꾸지 말 것). Git Bash heredoc은 백슬래시가 깨지니 파이썬 패치는 파일로.

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

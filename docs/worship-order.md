# 말씀 묵상 예배 — 순서와 음악 틀 (2026-10-24 확정)

> 목소리: 확정된 운영자 목소리(B + 생성 설정 ③) — [voice-onboarding.md](voice-onboarding.md)
> 화면: 지금 그대로(교회 프로젝터 자막). **숫자·영문은 낭독(normalize_ko·SPEAK_KO)과 표기(display_ref) 모두 주의**
> 저작권 근거: [research/2026-10-24_예배-찬송가-저작권.md](research/2026-10-24_예배-찬송가-저작권.md) · 함께 부를 곡 후보: [hymns-pd-list.md](hymns-pd-list.md)

## 순서 (약 25분, 넘으면 응답 찬양을 뺀다)

| # | 순서(id) | 내용 | 소리 |
|---|---|---|---|
| 1 | 예배의 부름 `call` | 여는 말 + 부름 | 운영자 목소리 |
| 2 | **함께 찬송** `song1` | 모두가 아는 저작권 만료 찬송, **운영자 직접 피아노 반주 + 가사 자막**(함께 따라 부르기) | 대장 `open` 자리 |
| 3 | 기도 `prayer` | 여는 기도 | 목소리 |
| 4 | 성경 봉독 `reading` | 개역한글(영어 KJV) 그대로 | 목소리 |
| 5 | 말씀 `sermon` | 설교(큐티 자료 기반) | 목소리 |
| 6 | 결단 기도 `closing` | | 목소리 |
| 7 | **응답 찬양** `song2` | **자작 찬송가**(찬송가 작법으로 만든 Suno 곡) 또는 자작 CCM | 대장 `response` 자리 |
| 8 | **기도회** `prayer_meeting` | 운영자가 인도 — "첫째, …를 위해 기도합시다" → **연주곡 위에서 40초 함께 기도** × 3 → 맺는 말 | 목소리 + 대장 `prayer` 연주곡(말할 땐 음악이 저절로 낮아짐) |
| 9 | 주기도문 `lords_prayer` | 고정 낭독(저장본 재사용) | 목소리 |
| 10 | 축복의 말씀 `blessing` | 민수기 6:24-26 | 목소리 |

## 나눠 맡기 (10-24 확정)

| | 맥미니 `worship-mac.sh` | 미니PC `worship-assemble.sh` |
|---|---|---|
| 하는 일 | 원고(Gemini) + **목소리**(낭독·기도회 인도) — 한 편 약 35분 | 찬송·기도회 배경 받기 → **합치기 → 자막 화면 → 영상** → 방송 정보 → (선택) 유튜브 예약 |
| 넘기는 것 | 목소리 묶음 `outbox/worship-voice/<날짜>_<언어>/`(script.json + 낭독 wav + bundle.json) → 자동 이관(10분 주기) | 받는 곳 `/mnt/external/macmini/<이관 묶음>/worship-voice/<날짜>_<언어>/` |
| 자막 | 문장마다 걸린 시간(qc.chunk_secs)을 script.json 에 담아 보냄 | 그 시간표로 화면·자막을 만든다(장·절 숫자 표기 포함) |
| 직접 연주 곡 | — | **`/mnt/external/nexis-worship/music/<곡>/`** 에 둔다(조립하는 곳) |

- 유튜브 방송 예약은 `SCHEDULE=1` 일 때만, 송출은 `worship-stream.sh`. **매일 자동 실행(크론)·유튜브 송출은 아직 끔**(사용자 10-24: 수동 시험까지만).
- 맥미니에서 전부 해 보려면 `FULL=1 bash worship-mac.sh …`(비교·비상용). 옛 미니PC 단독 방식 `worship-daily.sh` 는 비상용.

## 음악 대장 `scripts/worship/music.json`

곡마다 **종류·언어·권리 근거**를 적고, `license.status` 가 `verified` 인 곡만 예배에 나온다.

| 종류 `type` | 무엇 | 들어가는 자리 |
|---|---|---|
| `hymn_pd` | 함께 부르는 찬송 — 저작권 만료 곡, 운영자 직접 피아노 반주 + 가사 | `open`(1순위), `response`(대체) |
| `hymn_own` | 자작 찬송가 — 찬송가 작법으로 만든 자작곡(채널 업로드) | `open`(2순위), `response`(1순위) |
| `ccm` | 자작 CCM — 채널 보컬 곡(지금 79곡) | `response`(2순위), `open`(곡이 없을 때 대체) |
| `instrumental` | 연주곡 — 채널 연주곡(지금 43곡)·자작 찬송 연주판·직접 연주 | `prayer`(기도회 배경) |

- 같은 날 같은 곡이 두 번 나오지 않고, 날짜마다 돌아가며 고른다(`music_library.pick`).
- 채널 곡은 `python scripts/worship/music_library.py sync` 로 자동 반영(새 곡이 올라오면 다시 실행). **앨범 제목에 `찬송`/`Hymn` 이 있으면 보컬 곡은 자동으로 `hymn_own`**, `<제목> (연주)`·`(Instrumental)` 은 보컬판과 짝(→ 기도회 배경 우선). 손으로 바꾼 `type` 은 다음 sync 에도 유지. 작곡 규칙: [hymn-writing-guide.md](hymn-writing-guide.md)
- 현재 상태: `hymn_pd`·`hymn_own` 0곡 → 함께 찬송 자리는 당분간 CCM 이 대신 나온다.

## 곡 보내는 법 (직접 연주 · 자작곡)

**미니PC** `/mnt/external/nexis-worship/music/<곡-id>/` 에 아래를 둔다(조립을 미니PC 가 하므로 — 보내 주시면 제가 넣음).

```
music/amazing-grace-piano/
  audio.mp3        피아노 반주 녹음(또는 자작곡 음원)
  lyrics.txt       가사 — 절마다 빈 줄로 구분. 절 첫 줄에 '@0:12' 처럼 시작 시각을 적으면 그대로, 없으면 고르게 나눔
  meta.json        아래 예시
```

```json
{
 "id": "local:amazing-grace-piano",
 "title": "나 같은 죄인 살리신 (Amazing Grace)",
 "type": "hymn_pd",
 "lang": "ko",
 "file": "audio.mp3",
 "lyrics": "lyrics.txt",
 "credits": {"lyricist": "John Newton(1807)", "composer": "NEW BRITAIN, 미국 민요(1829)", "arranger": "운영자 피아노", "translator": "확인 필요"},
 "license": {"status": "pending", "basis": "선율·원가사 저작권 만료, 한국어 가사 확인 중", "evidence": "https://hymnary.org/text/amazing_grace_how_sweet_the_sound"}
}
```

그다음 `python scripts/worship/music_library.py add ~/Work/nexis-worship/music/amazing-grace-piano`. 한국어 가사 권리를 확인하기 전에는 `status` 를 `pending` 으로 둔다(→ 예배에 안 나옴). 반주만 쓸 때는 `lyrics` 를 빼고 `verified`.

## 기도회 세부

- 원고: Gemini 가 `prayer_meeting.intro / topics[3] / close` 를 함께 쓴다(첫째 = 오늘 말씀을 삶으로, 둘째 = 가정·이웃·아픈 이, 셋째 = 교회·나라·세상).
- 함께 기도하는 시간: 제목마다 `WORSHIP_PRAY_SEC`(기본 40초).
- 배경 연주곡은 기도회 전체에 깔리고, 인도할 때만 낮아진다(sidechain). 시작 2.5초·끝 4초 페이드.
- 화면: 인도 문장 자막 → 기도 시간엔 "함께 기도합니다" + 그 제목. 설명란 챕터에 '기도 제목 1·2·3'.

## 설명란 음악 표기 (자동)

`🎵 <순서>: <곡명> — 작사·작곡·반주(직접 연주)·공개저작물` 또는 `— Still Waters (yojosuknam) <유튜브 주소>`.

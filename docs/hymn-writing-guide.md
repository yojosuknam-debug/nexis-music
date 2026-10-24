# 자작 찬송가 — 예배 쪽 안내

**작곡 규칙의 원본은 곡을 만드는 저장소에 둔다** — 한 곳에서만 고쳐야 꼬이지 않는다.

| 무엇 | 어디 |
|---|---|
| 작곡 규격 Hymn v1.0 · Suno 프롬프트 · 연주판 · 앨범 제목 규칙 · 점검표 | `D:\YH\APP\youtube-playlist\suno-playlist-video\docs\album-system\40_genres\hymn.md` (youtube-playlist 앨범 시스템의 장르 가이드) |
| 근거 조사 | [research/2026-10-24_찬송가-작법-선정기준.md](research/2026-10-24_찬송가-작법-선정기준.md) |
| 가사 음절·구조 검사기 | `python scripts/worship/hymn_check.py <가사.txt> [--meter 8.8.8.8]` |
| 예배에 들어가는 방식 | [worship-order.md](worship-order.md) |

## 흐름 (만들기 → 예배까지)

1. youtube-playlist 에서 "Still Waters 찬송가 앨범 만들어줘" → `00_PLAYBOOK.md` + `40_genres/hymn.md` 로 5파일 생성(`album-drafts/`).
2. 가사마다 `hymn_check.py` 통과(❌ 0개) → Suno 작곡(보컬판) → stems 로 연주판.
3. 기존 파이프라인 그대로 `input/` → 미니PC `/run` 또는 `/alltracks` → 채널 업로드 → 음악 사이트 반영.
4. 예배 쪽에서 `python scripts/worship/music_library.py sync`:
   - 앨범 제목에 `찬송`/`Hymn` → 보컬 곡을 `hymn_own`(자작 찬송가)으로
   - `<제목> (연주)` / `(Instrumental)` → 같은 앨범 보컬판과 짝 → 그날 응답 찬송의 연주판이 기도회 배경으로 먼저 나온다
5. 대장(`music.json`) 커밋 → 맥미니·미니PC `git pull`.

"""
4단계 — 앨범 페이지 생성 (Aurora Glass)

catalog.json → public/album/ 아래 정적 HTML.

  public/album/jukebox.css     공용 스타일
  public/album/jukebox.js      공용 재생기
  public/album/<slug>.html     앨범 페이지 (자기 데이터만 인라인)
  public/album/index.html      앨범 목록

Next.js 라우팅을 건드리지 않는다. public/ 아래 정적 파일이라 그대로 서비스된다.

🔴 CSS·JS·링크는 **루트 절대경로(/album/...)** 로 쓴다. 상대경로(./)로 쓰면
   Vercel 이 /album/ → /album 으로 리다이렉트할 때 한 단계 위로 해석돼
   목록 페이지가 통째로 무스타일이 된다(2026-09-02 실제 발생).

강조색은 **빌드 시점에 커버에서 뽑아 CSS 변수로 박는다.** 브라우저에서 canvas 로 뽑으면
이미지가 다른 도메인(R2)이라 CORS 설정에 의존하게 되고, 첫 화면이 무채색으로 깜빡인다.

사용법:
    python scripts/jukebox/build_pages.py
"""
from __future__ import annotations

import colorsys
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CATALOG = HERE / "catalog.json"
COVERS = HERE / "assets" / "covers"
OUT = REPO / "public" / "album"

SITE = "https://music.yojosuknam.com"
FONTS = ("https://fonts.googleapis.com/css2?"
         "family=IBM+Plex+Sans+KR:wght@300;400;500;600&family=Instrument+Serif&display=swap")


# ── 커버에서 강조색 뽑기 ──────────────────────────────────────────────────
def accent_of(path: Path) -> tuple[int, int, int]:
    """채도가 있는 화소만 모아 평균낸다. 무채색·너무 어두운 화소는 결과를 탁하게 만들어 버린다."""
    im = Image.open(path).convert("RGB").resize((32, 32), Image.LANCZOS)
    raw = im.tobytes()                      # getdata() 는 Pillow 14 에서 사라진다
    rs = gs = bs = n = 0.0
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        mx, mn = max(r, g, b), min(r, g, b)
        sat = 0 if mx == 0 else (mx - mn) / mx
        if sat < 0.18 or mx < 40 or mn > 232:
            continue
        w = sat * sat
        rs += r * w; gs += g * w; bs += b * w; n += w
    if n < 1:
        return (143, 179, 164)
    h, l, s = colorsys.rgb_to_hls(rs / n / 255, gs / n / 255, bs / n / 255)
    s = min(0.92, max(0.55, s))          # 너무 흐리거나 형광이 되지 않게 가둔다
    l = min(0.70, max(0.52, l))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (round(r * 255), round(g * 255), round(b * 255))


def clean_album_title(title: str) -> str:
    """제목 끝의 채널 설명을 뗀다 — 'ABOVE THE TREELINE — Lo-fi & Chill Album' → 'ABOVE THE TREELINE'.
    'Bible Pansori Vol.1 — Three Sacred Tales' 처럼 진짜 부제는 남긴다:
    'Album/앨범' 로 끝나거나 'Channel/채널' 이 든 꼬리만 제거한다.
    슬러그는 건드리지 않으므로 URL 은 그대로다."""
    parts = re.split(r"\s+[—–]\s+", title)
    if len(parts) < 2:
        return title.strip()
    tail = parts[-1].strip()
    if re.search(r"(?:Album|앨범)$", tail, re.I) or re.search(r"(?:Channel|채널)", tail, re.I):
        return " — ".join(x.strip() for x in parts[:-1]).strip() or title.strip()
    return title.strip()


def mmss(ms: int) -> str:
    s = round(ms / 1000)
    return f"{s // 60}:{s % 60:02d}"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ── 페이지 ────────────────────────────────────────────────────────────────
def album_page(a: dict, accent: tuple[int, int, int]) -> str:
    # 음원이 없는 트랙은 목록에 넣지 않는다 — 눌러도 안 나는 곡은 고장으로 보인다
    disp = clean_album_title(a["title"])
    playable = [t for t in a["tracks"] if t.get("url")]
    sung = sum(1 for t in playable if t.get("lyrics"))
    total_ms = sum(t["ms"] for t in playable)
    runtime = f"{round(total_ms/60000)}분"
    desc = (f"{disp} — {len(playable)}곡 · {runtime}"
            + (f" · 가사 수록 {sung}곡" if sung else " · 전곡 연주"))
    data = {
        "title": disp,
        "cover": a.get("cover_url", ""),
        "tracks": [{"n": t["n"], "title": t["title"], "ms": t["ms"],
                    "url": t["url"], "lyrics": t.get("lyrics", []),
                    "instrumental": t.get("instrumental", False)}
                   for t in playable],
    }
    r, g, b = accent
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(disp)} — 넥시스 뮤직</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}/album/{a['slug']}.html">
<meta property="og:type" content="music.album">
<meta property="og:title" content="{esc(disp)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{esc(a.get('cover_url',''))}">
<meta property="og:url" content="{SITE}/album/{a['slug']}.html">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/album/jukebox.css">
<style>:root{{--accent:rgb({r},{g},{b});--accent-rgb:{r},{g},{b}}}</style>
</head>
<body>
<div class="bg" style="background-image:url('{esc(a.get('cover_url',''))}')"></div>
<div class="veil"></div>

<header class="top">
  <a class="back" href="/index.html">← 아카이브</a>
</header>

<main class="wrap">
  <div class="art">
    <img src="{esc(a.get('cover_url',''))}" alt="{esc(disp)} 앨범 커버" width="800" height="800">
    <p class="genre">{esc(a.get('genre',''))}</p>
    <p class="mood">{esc('가사 수록 ' + str(sung) + '곡' if sung else '전곡 연주')}</p>
  </div>

  <div class="main">
    <h1>{esc(disp)}</h1>
    <p class="sub"><b>{len(playable)}곡</b> · {runtime}</p>

    <div class="transport">
      <button class="play" id="play" aria-label="재생"></button>
      <div class="scrub">
        <div class="now" id="now"></div>
        <div class="rail" id="rail"><div class="fill" id="fill"></div></div>
        <div class="clock"><span id="cur">0:00</span><span id="dur">0:00</span></div>
      </div>
    </div>

    <div class="seg">
      <button id="tabList" aria-selected="true">수록곡</button>
      <button id="tabLyr" aria-selected="false">가사</button>
    </div>
    <div class="list" id="list"></div>
    <div class="list lyr" id="lyrics" hidden></div>
  </div>
</main>

<audio id="audio" preload="none"></audio>
<script>window.ALBUM = {json.dumps(data, ensure_ascii=False)};</script>
<script src="/album/jukebox.js"></script>
</body>
</html>
"""


def playable_count(a: dict) -> int:
    return sum(1 for t in a["tracks"] if t.get("url"))


def playable_ms(a: dict) -> int:
    return sum(t["ms"] for t in a["tracks"] if t.get("url"))


def index_page(albums: list[dict], accents: dict[str, tuple]) -> str:
    cards = []
    for a in sorted(albums, key=lambda x: clean_album_title(x["title"]).lower()):
        r, g, b = accents[a["slug"]]
        cards.append(
            f'<a class="card" href="/album/{a["slug"]}.html" style="--accent-rgb:{r},{g},{b}">'
            f'<img src="{esc(a.get("cover_url",""))}" alt="" loading="lazy" width="800" height="800">'
            f'<span class="t">{esc(clean_album_title(a["title"]))}</span>'
            f'<span class="m">{playable_count(a)}곡 · {round(playable_ms(a)/60000)}분</span></a>')
    total_tracks = sum(playable_count(a) for a in albums)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>앨범 — 넥시스 뮤직</title>
<meta name="description" content="앨범 {len(albums)}장 · {total_tracks}곡. 곡을 눌러 바로 듣고 가사를 봅니다.">
<link rel="canonical" href="{SITE}/album/">
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="/album/jukebox.css">
</head>
<body class="gallery">
<header class="top"><a class="back" href="/index.html">← 아카이브</a></header>
<div class="gwrap">
  <h1 class="gtitle">앨범</h1>
  <p class="gsub">{len(albums)}장 · {total_tracks}곡</p>
  <div class="grid">{''.join(cards)}</div>
</div>
</body>
</html>
"""


def main() -> int:
    if not CATALOG.exists():
        print("[에러] catalog.json 이 없습니다.")
        return 1
    albums = json.loads(CATALOG.read_text(encoding="utf-8"))
    ready = [a for a in albums if a.get("cover_url") and any(t.get("url") for t in a["tracks"])]
    if not ready:
        print("[에러] 업로드된 앨범이 없습니다. upload_r2.py 를 먼저 실행하세요.")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "jukebox.css").write_text(CSS, encoding="utf-8")
    (OUT / "jukebox.js").write_text(JS, encoding="utf-8")

    accents = {}
    for a in ready:
        cf = COVERS / a.get("cover_file", "")
        accents[a["slug"]] = accent_of(cf) if cf.exists() else (143, 179, 164)
        (OUT / f"{a['slug']}.html").write_text(album_page(a, accents[a["slug"]]), encoding="utf-8")
    (OUT / "index.html").write_text(index_page(ready, accents), encoding="utf-8")

    # 더 이상 발행 대상이 아닌 페이지를 지운다.
    # 이게 없으면 .nojukebox 를 붙여도 예전 페이지가 그대로 살아 있어 "비공개"가 되지 않는다.
    keep = {f"{a['slug']}.html" for a in ready} | {"index.html"}
    removed = []
    for f in OUT.glob("*.html"):
        if f.name not in keep:
            f.unlink()
            removed.append(f.name)

    skipped = len(albums) - len(ready)
    print(f"앨범 페이지 {len(ready)}개 생성 → public/album/")
    if skipped:
        print(f"  (업로드 안 된 앨범 {skipped}개는 건너뜀)")
    if removed:
        print(f"  제외되어 페이지 삭제 {len(removed)}개: " + ", ".join(removed[:5])
              + (" …" if len(removed) > 5 else ""))
        print("   ※ R2 의 음원 파일은 남아 있습니다(페이지에서 링크만 끊김).")
    return 0


CSS = r"""
/* Aurora Glass — 앨범아트가 배경을 물들이는 프로스티드 글래스.
   페이지마다 --accent 가 빌드 시점에 커버에서 뽑혀 박힌다. */
*{box-sizing:border-box}
html{background:#0d0f14}
body{margin:0;min-height:100vh;background:#0d0f14;color:#fff;
  font-family:"IBM Plex Sans KR","Malgun Gothic",system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;overflow-x:hidden}
button{font:inherit;color:inherit;background:none;border:none;cursor:pointer}
a{color:inherit;text-decoration:none}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:6px}

.bg{position:fixed;inset:-25%;z-index:-2;background-size:cover;background-position:center;
  filter:blur(90px) saturate(200%) brightness(.85);transform:scale(1.25)}
.veil{position:fixed;inset:0;z-index:-1;
  background:radial-gradient(120% 90% at 20% 0%,rgba(0,0,0,.10),rgba(0,0,0,.74) 75%)}

.top{padding:20px clamp(16px,4vw,40px) 0;max-width:1080px;margin:0 auto}
.back{font-size:13px;color:rgba(255,255,255,.62);transition:color .16s}
.back:hover{color:#fff}

.wrap{max-width:1080px;margin:0 auto;padding:clamp(20px,4vw,48px) clamp(16px,4vw,40px) 80px;
  display:grid;gap:clamp(24px,4vw,52px);grid-template-columns:minmax(0,340px) minmax(0,1fr);
  align-items:start}
@media(max-width:820px){.wrap{grid-template-columns:1fr}}

.art img{width:100%;height:auto;aspect-ratio:1;object-fit:cover;border-radius:20px;display:block;
  box-shadow:0 30px 70px -20px rgba(0,0,0,.75),0 0 0 1px rgba(255,255,255,.10) inset;
  background:rgba(255,255,255,.05)}
.genre{margin:18px 0 0;font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:rgba(255,255,255,.62);line-height:1.7}
.mood{margin:8px 0 0;font-size:13px;line-height:1.65;color:rgba(255,255,255,.50);font-weight:300}

h1{font-family:"Instrument Serif",Georgia,serif;font-weight:400;
  font-size:clamp(30px,6.2vw,68px);line-height:1.03;margin:0;letter-spacing:-.015em;
  text-wrap:balance;overflow-wrap:anywhere}
.sub{margin:12px 0 0;font-size:13.5px;color:rgba(255,255,255,.66);font-weight:300}
.sub b{color:var(--accent);font-weight:500}

.transport{display:flex;align-items:center;gap:18px;margin:28px 0 22px}
.play{width:60px;height:60px;border-radius:50%;background:var(--accent);display:grid;
  place-items:center;color:#0d0f14;flex:0 0 auto;transition:transform .16s;
  box-shadow:0 12px 34px -8px rgba(var(--accent-rgb),.70)}
.play:hover{transform:scale(1.06)}
.play svg{width:22px;height:22px;fill:currentColor}
.scrub{flex:1;min-width:0}
.now{font-size:14px;font-weight:500;margin-bottom:9px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.rail{height:4px;border-radius:99px;background:rgba(255,255,255,.20);position:relative;cursor:pointer}
.fill{position:absolute;inset:0 auto 0 0;width:0%;border-radius:99px;background:var(--accent)}
.clock{display:flex;justify-content:space-between;font-size:11px;margin-top:7px;
  color:rgba(255,255,255,.52);font-variant-numeric:tabular-nums}

.seg{display:inline-flex;gap:2px;background:rgba(255,255,255,.10);padding:3px;
  border-radius:99px;margin-bottom:14px}
.seg button{padding:6px 17px;border-radius:99px;font-size:12.5px;color:rgba(255,255,255,.60);
  transition:background .16s,color .16s}
.seg button[aria-selected="true"]{background:rgba(255,255,255,.94);color:#14161c;font-weight:500}

.list{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11);
  border-radius:18px;padding:8px;backdrop-filter:blur(28px) saturate(180%);
  -webkit-backdrop-filter:blur(28px) saturate(180%)}
.trk{display:grid;grid-template-columns:26px minmax(0,1fr) auto;gap:14px;align-items:center;
  width:100%;text-align:left;padding:12px 14px;border-radius:12px;color:rgba(255,255,255,.88);
  transition:background .16s;min-width:0}
.trk:hover{background:rgba(255,255,255,.09)}
.trk[aria-current="true"]{background:rgba(var(--accent-rgb),.18)}
.trk .n{font-size:12px;color:rgba(255,255,255,.45);font-variant-numeric:tabular-nums}
.trk[aria-current="true"] .n{color:var(--accent)}
.trk .t{font-size:14.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trk .d{font-size:12px;color:rgba(255,255,255,.45);font-variant-numeric:tabular-nums}

.eq{display:inline-flex;gap:2px;align-items:flex-end;height:11px}
.eq i{width:2px;background:var(--accent);border-radius:1px;animation:eqb .9s ease-in-out infinite}
.eq i:nth-child(2){animation-delay:.15s}
.eq i:nth-child(3){animation-delay:.3s}
@keyframes eqb{0%,100%{height:3px}50%{height:11px}}
@media (prefers-reduced-motion:reduce){.eq i{animation:none;height:7px}}

.lyr{padding:26px 28px}
.lyr .head{font-family:"Instrument Serif",Georgia,serif;font-size:26px;color:#fff;
  margin-bottom:16px;line-height:1.2}
.lyr .sec{margin-bottom:22px}
.lyr .tag{font-size:10.5px;letter-spacing:.18em;color:var(--accent);text-transform:uppercase;
  margin-bottom:5px}
.lyr .ln{font-size:15px;line-height:1.95;color:rgba(255,255,255,.86);font-weight:300}
.lyr .empty{font-size:14px;color:rgba(255,255,255,.52);font-weight:300;margin:0}
@media(max-width:560px){.lyr{padding:20px}}

/* ── 앨범 목록 ── */
.gallery .bg,.gallery .veil{display:none}
.gwrap{max-width:1180px;margin:0 auto;padding:24px clamp(16px,4vw,40px) 80px}
.gtitle{font-family:"Instrument Serif",Georgia,serif;font-size:clamp(34px,7vw,60px);margin:14px 0 0}
.gsub{color:rgba(255,255,255,.55);font-size:13px;margin:6px 0 30px;font-weight:300}
.grid{display:grid;gap:20px;grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}
.card{display:flex;flex-direction:column;gap:9px}
.card img{width:100%;height:auto;aspect-ratio:1;object-fit:cover;border-radius:14px;display:block;
  background:rgba(255,255,255,.05);transition:transform .2s,box-shadow .2s}
.card:hover img{transform:translateY(-4px);box-shadow:0 18px 40px -14px rgba(var(--accent-rgb),.6)}
.card .t{font-size:14px;line-height:1.4;overflow-wrap:anywhere}
.card .m{font-size:11.5px;color:rgba(255,255,255,.48)}
/* 폰에서 minmax(170px,1fr)+gap 20 은 390px 폭에 2열이 안 들어가 1열로 떨어진다.
   107장이 세로로 늘어서면 목록 구실을 못 하므로 폰은 2열로 못박는다. */
@media(max-width:560px){.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
  .card .t{font-size:13px}.gwrap{padding-bottom:60px}}
"""

JS = r"""
/* Aurora Glass 재생기 — 페이지에 인라인된 window.ALBUM 하나만 다룬다. */
(function () {
  "use strict";
  var A = window.ALBUM || { tracks: [] };
  var PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
  var PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>';
  var $ = function (id) { return document.getElementById(id); };
  var audio = $("audio"), idx = 0, playing = false;

  function mmss(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    var m = Math.floor(sec / 60), s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? "0" + s : s);
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function renderList() {
    var host = $("list");
    host.innerHTML = "";
    A.tracks.forEach(function (t, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "trk";
      b.dataset.i = i;
      b.innerHTML = '<span class="n">' + (t.n < 10 ? "0" + t.n : t.n) + "</span>" +
        '<span class="t">' + esc(t.title) + "</span>" +
        '<span class="d">' + mmss(t.ms / 1000) + "</span>";
      b.addEventListener("click", function () { select(i, true); });
      host.appendChild(b);
    });
  }

  function renderLyrics() {
    var t = A.tracks[idx], host = $("lyrics");
    if (!t.lyrics || !t.lyrics.length) {
      host.innerHTML = '<p class="empty">' +
        (t.instrumental ? "가사가 없는 연주곡입니다." : "가사가 준비되지 않았습니다.") + "</p>";
      return;
    }
    var out = ['<div class="head">' + esc(t.title) + "</div>"];
    t.lyrics.forEach(function (s) {
      out.push('<div class="sec">' +
        (s.tag ? '<div class="tag">' + esc(s.tag) + "</div>" : "") +
        s.lines.map(function (l) { return '<div class="ln">' + esc(l) + "</div>"; }).join("") +
        "</div>");
    });
    host.innerHTML = out.join("");
  }

  function select(i, autoplay) {
    idx = i;
    var t = A.tracks[i];
    document.querySelectorAll(".trk").forEach(function (row) {
      row.setAttribute("aria-current", Number(row.dataset.i) === i ? "true" : "false");
    });
    $("now").textContent = t.title;
    $("dur").textContent = mmss(t.ms / 1000);
    $("cur").textContent = "0:00";
    $("fill").style.width = "0%";
    renderLyrics();
    if (audio.src !== t.url) audio.src = t.url;
    if (autoplay) { audio.currentTime = 0; play(); } else { setPlaying(false); }
  }

  function play() {
    audio.play().then(function () { setPlaying(true); })
                .catch(function () { setPlaying(false); });
  }
  function setPlaying(on) {
    playing = on;
    $("play").innerHTML = on ? PAUSE : PLAY;
    $("play").setAttribute("aria-label", on ? "일시정지" : "재생");
    var cell = document.querySelector('.trk[aria-current="true"] .n');
    if (cell) {
      var t = A.tracks[idx];
      cell.innerHTML = on ? '<span class="eq"><i></i><i></i><i></i></span>'
                          : (t.n < 10 ? "0" + t.n : String(t.n));
    }
  }

  $("play").addEventListener("click", function () {
    if (audio.paused) play(); else { audio.pause(); setPlaying(false); }
  });
  audio.addEventListener("timeupdate", function () {
    var d = audio.duration;
    if (!isFinite(d) || !d) return;
    $("fill").style.width = (audio.currentTime / d * 100).toFixed(2) + "%";
    $("cur").textContent = mmss(audio.currentTime);
  });
  audio.addEventListener("loadedmetadata", function () {
    if (isFinite(audio.duration)) $("dur").textContent = mmss(audio.duration);
  });
  audio.addEventListener("ended", function () {
    if (idx < A.tracks.length - 1) select(idx + 1, true); else setPlaying(false);
  });
  $("rail").addEventListener("click", function (ev) {
    var r = this.getBoundingClientRect();
    if (isFinite(audio.duration)) {
      audio.currentTime = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)) * audio.duration;
    }
  });

  function pane(which) {
    $("list").hidden = which !== "list";
    $("lyrics").hidden = which !== "lyrics";
    $("tabList").setAttribute("aria-selected", which === "list" ? "true" : "false");
    $("tabLyr").setAttribute("aria-selected", which === "lyrics" ? "true" : "false");
  }
  $("tabList").addEventListener("click", function () { pane("list"); });
  $("tabLyr").addEventListener("click", function () { pane("lyrics"); });

  renderList();
  select(0, false);
  setPlaying(false);
})();
"""

if __name__ == "__main__":
    sys.exit(main())

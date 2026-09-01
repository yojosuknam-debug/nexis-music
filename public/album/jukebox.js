
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

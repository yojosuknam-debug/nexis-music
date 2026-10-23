"""
말씀 묵상 예배(20분 이내) 한 편 만들기 — 말씀Log 큐티(2,000개 자료 또는 API) → 원고 → 내 목소리 낭독 → 찬양 2곡과 이어 붙인 mp3.

    python scripts/worship/build_worship.py --lang ko            # 원고만(script.json)
    D:/YH/voice-lab/.venv/Scripts/python scripts/worship/build_worship.py --lang ko --voice --mix

순서(주보): 여는 말·예배의 부름 → 찬양 1 → 기도 → 성경 봉독 → 말씀 → 결단 기도 → 찬양 2 → 주기도문 → 축복의 말씀
- 성경 본문은 말씀Log 가 준 역본(한국어 개역한글, 영어 KJV) 그대로 — AI 가 고치지 않는다
- 축도는 하지 않는다(사용자 결정 10-22) → 민수기 6:24-26 '축복의 말씀' 낭독
- 주기도문·축복의 말씀은 고정 글이라 한 번 만든 음성을 다시 쓴다(cache/)
- 목소리 = Chatterbox 다국어(무료·CPU) + 사용자 녹음. 묶음마다 Whisper 로 되읽어 틀리면 다시 만든다

키는 레포 루트 .env.local(sync-env.ps1 nexis-music)에서 읽고 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("WORSHIP_OUT", ROOT / "output" / "worship"))
CACHE = OUT / "cache"
VOICE_DIR = Path(os.environ.get("WORSHIP_REF_DIR", r"D:\YH\voice-lab\ref"))   # 사용자 녹음(레포 밖, 비공개)
THREADS = int(os.environ.get("WORSHIP_THREADS", "8"))   # 미니PC 는 3 (다른 서비스 몫을 남긴다)
DEVICE = os.environ.get("WORSHIP_DEVICE", "cpu")   # 맥미니 = mps(Apple GPU). Whisper 는 MPS 미지원이라 늘 CPU
REF = {"ko": "my_ko2.wav", "en": "my_en.wav"}   # 한국어 = 새로운 녹음 29(10-23 사용자 선택 '억양 3')
QT_URL = "https://qt.yojosuknam.com/api/generate-qt"
# 한국어 원고의 바탕 = 말씀Log 큐티 2,000개(autovid data/qt_data.json) 중 개역한글 검증 항목(qt-insta eligible_ids).
# qt-insta 와 같은 순서표라 같은 날 인스타 카드와 같은 본문이 된다(10-23 사용자). 파일이 없으면 위 API.
QT_DATA = os.environ.get("WORSHIP_QT_DATA", "")
QT_ELIGIBLE = os.environ.get("WORSHIP_QT_ELIGIBLE", "")
QT_START, QT_ORDER_SEED = dt.date(2026, 9, 15), "malsseumlog-insta-v1"   # qt_insta.py 의 START·ORDER_SEED 와 같아야 함
RADIO_JSON = "https://music.yojosuknam.com/album/radio.json"
TEXT_MODEL = "gemini-3.1-pro-preview"   # 2.5-pro 는 신규 사용 불가(10-22 404)
MAX_MIN = 20.0
UA = "Mozilla/5.0 NexisWorship/1.0"

# 억양: '구연동화 같다'(10-22) → 감정 강도를 낮추고 2~3문장씩 묶어 만든다
EXAGGERATION, CFG = 0.25, 0.5
CHUNK_CHARS = {"ko": 150, "en": 260}
SPEED = 0.92            # "조금 느리게"(10-23) — 다 만든 음성을 음높이 그대로 늘린다(atempo)
MAX_ERR = 0.12          # 되읽기 오류율이 이보다 높으면 다시 만든다
TRIES = 3

FIXED = {
    "ko": {
        "lords_prayer": ("다 함께 주님 가르쳐 주신 기도로 마음을 모읍니다. "
                         "하늘에 계신 우리 아버지여, 이름이 거룩히 여김을 받으시오며, 나라이 임하옵시며, "
                         "뜻이 하늘에서 이룬 것 같이 땅에서도 이루어지이다. 오늘날 우리에게 일용할 양식을 주옵시고, "
                         "우리가 우리에게 죄 지은 자를 사하여 준 것 같이 우리 죄를 사하여 주옵시고, "
                         "우리를 시험에 들게 하지 마옵시고, 다만 악에서 구하옵소서. "
                         "대개 나라와 권세와 영광이 아버지께 영원히 있사옵나이다. 아멘."),
        "blessing": ("축복의 말씀으로 오늘 예배를 마칩니다. "
                     "여호와는 네게 복을 주시고 너를 지키시기를 원하며, 여호와는 그 얼굴로 네게 비취사 은혜 베푸시기를 원하며, "
                     "여호와는 그 얼굴을 네게로 향하여 드사 평강 주시기를 원하노라. 민수기 육장 이십사절에서 이십육절 말씀입니다. "
                     "이 말씀이 오늘 여러분의 하루 위에 머물기를 바랍니다."),
    },
    "en": {
        "lords_prayer": ("Let us pray together the prayer our Lord taught us. "
                         "Our Father, which art in heaven, hallowed be thy name. Thy kingdom come, thy will be done in earth, "
                         "as it is in heaven. Give us this day our daily bread. And forgive us our debts, as we forgive our debtors. "
                         "And lead us not into temptation, but deliver us from evil: for thine is the kingdom, and the power, "
                         "and the glory, for ever. Amen."),
        "blessing": ("We close with words of blessing. "
                     "The Lord bless thee, and keep thee: the Lord make his face shine upon thee, and be gracious unto thee: "
                     "the Lord lift up his countenance upon thee, and give thee peace. Numbers chapter six, verses twenty-four to twenty-six. "
                     "May these words rest upon your day."),
    },
}
OPENING = {
    "ko": "이 시간은 말씀Log와 함께하는 말씀 묵상 예배입니다. 설교와 기도는 AI의 도움으로 준비되었습니다.",
    "en": "Welcome to this time of worship with Malsseum Log. The sermon and prayers were prepared with the help of AI.",
}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def env() -> dict[str, str]:
    out = {}
    for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def http_json(url: str, body: dict | None = None, headers: dict | None = None, timeout: int = 300):
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": UA, **({"Content-Type": "application/json"} if data else {}), **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 숫자 읽기 ─────────────────────────────────────────────────────────────
def sino(n: int) -> str:
    """한자어 수(교회는 '사 장 십삼 절'로 읽는다 — 고유어 '네 장'이 아니다)."""
    d = "영일이삼사오육칠팔구"
    if n == 0:
        return "영"
    out = ""
    for unit, name in ((100, "백"), (10, "십")):
        q, n = divmod(n, unit)
        if q:
            out += ("" if q == 1 else d[q]) + name
    return out + (d[n] if n else "")


EN_NUM = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
          "seventeen eighteen nineteen").split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def en_num(n: int) -> str:
    if n < 20:
        return EN_NUM[n]
    if n < 100:
        t, o = divmod(n, 10)
        return EN_TENS[t] + (f"-{EN_NUM[o]}" if o else "")
    h, r = divmod(n, 100)
    return f"{EN_NUM[h]} hundred" + (f" {en_num(r)}" if r else "")


def speak_ref(ref: str, lang: str) -> str:
    """'요한복음 4:13-15' → '요한복음 사장 십삼절에서 십오절' / 'Proverbs 18:10-12' → 'Proverbs chapter eighteen, verses ten to twelve'"""
    m = re.match(r"^(.*?)\s*(\d+):(\d+)(?:\s*[-~]\s*(\d+))?$", ref.strip())
    if not m:
        return ref
    book, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    if lang == "ko":
        return f"{book} {sino(ch)}장 {sino(v1)}절" + (f"에서 {sino(int(v2))}절" if v2 else "")
    return f"{book} chapter {en_num(ch)}, " + (f"verses {en_num(v1)} to {en_num(int(v2))}" if v2 else f"verse {en_num(v1)}")


# ── 1) 원고 ───────────────────────────────────────────────────────────────
PROMPT = {
    "ko": """당신은 작은 교회의 따뜻하고 담백한 목회자입니다. 아래 오늘의 큐티 자료로, 라디오처럼 혼자 듣는 사람을 위한
20분 말씀 묵상 예배의 낭독 원고를 씁니다. 반드시 JSON 하나만 출력하세요.

{{"call": "예배의 부름 — 3~4문장. 듣는 이를 예배로 초대하고 마지막 문장은 찬양으로 마음을 열자는 말",
  "prayer": "여는 기도 — 350~450자. 감사·고백·말씀을 사모하는 마음, '예수님의 이름으로 기도합니다. 아멘.'으로 끝",
  "sermon": "말씀 — 2,000~2,300자. 도입 → 세 가지 요점 → 맺음. 오늘 본문 구절만 인용",
  "song2_intro": "결단 기도 뒤 응답 찬양으로 넘어가는 한 문장"}}

규칙:
- 소리 내어 읽을 글입니다. 괄호·따옴표·번호표·'첫째:' 같은 표기·이모지를 쓰지 말고 말로 풀어 쓰세요.
- 숫자는 아라비아 숫자를 쓰지 말고 한글로 쓰세요. 성경 장절 표기(4:13 등)는 쓰지 마세요.
- 오늘 본문 말고 다른 성경 구절을 직접 인용하지 마세요(틀린 인용 방지).
- 과장된 감탄, 설교 상투어 반복, 특정 교단·정치·헌금 이야기를 피하세요. 담담하고 따뜻하게.
- 문장은 짧게(한 문장 60자 안팎).

제목: {title}
본문: {ref}
{verses}
요약: {summary}
말씀Log 설교 초안: {sermon}
묵상: {meditation}
적용: {application}""",
    "en": """You are a warm, plain-spoken pastor of a small church. Using today's devotional material below, write the spoken
script for a 20-minute worship service for someone listening alone, like radio. Output a single JSON object only.

{{"call": "call to worship — 3 to 4 sentences, ending with an invitation to open our hearts in song",
  "prayer": "opening prayer — 150 to 200 words, thanksgiving, confession, longing for the word; end with 'In Jesus' name we pray. Amen.'",
  "sermon": "sermon — 1,000 to 1,150 words. introduction, three points, conclusion. Quote only today's verses",
  "song2_intro": "one sentence leading from the closing prayer into a response song"}}

Rules:
- This will be read aloud. No brackets, quotation marks, bullet labels like 'First:', or emoji; write it as speech.
- Write numbers as words. Do not write chapter:verse notation.
- Do not quote any Bible verse other than today's passage (to avoid misquotes).
- Avoid exaggerated exclamations, cliches, denominational, political or offering talk. Calm and warm.
- Keep sentences short.

Title: {title}
Passage: {ref}
{verses}
Summary: {summary}
Draft sermon: {sermon}
Meditation: {meditation}
Application: {application}""",
}


def gemini_json(key: str, prompt: str) -> dict:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}
    d = http_json(f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent",
                  body, {"x-goog-api-key": key}, timeout=600)
    return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])


def clean_speech(s: str) -> str:
    s = re.sub(r"[\"'“”‘’()\[\]*#]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def pick_songs(lang: str, day: dt.date) -> list[dict]:
    """찬양 2곡 — Still Waters 채널의 가사 있는 곡. 한국어 날은 한국어 가사 곡(지금은 '천막 아래' 7곡)."""
    data = http_json(RADIO_JSON)
    pool = []
    for a in data["albums"]:
        if a.get("station") != "Still Waters":
            continue
        for t in a["tracks"]:
            pool.append({**t, "album": a["title"], "slug": a["slug"], "page": a["page"], "cover": a["cover"]})
    lyr = json.loads((HERE / "songs.json").read_text(encoding="utf-8"))   # 가사 언어 표(곡 고르기용)
    ok = {(s["slug"], s["n"]) for s in lyr if s["lang"] == lang}
    cand = [t for t in pool if (t["slug"], t["n"]) in ok and 120_000 <= int(t.get("ms") or 0) <= 300_000]
    cand.sort(key=lambda t: (t["slug"], t["n"]))
    if len(cand) < 2:
        raise RuntimeError(f"{lang} 찬양 후보가 부족합니다({len(cand)}곡)")
    i = day.toordinal() * 2 % len(cand)
    return [cand[i], cand[(i + 1) % len(cand)]]


def qt_from_data(day: dt.date) -> dict:
    """그날의 큐티 1개 — qt_insta.py schedule()·adapt() 와 같은 규칙(구절 표기를 '책 장:절'로 통일)."""
    items = {i["id"]: i for i in json.loads(Path(QT_DATA).read_text(encoding="utf-8"))["items"]}
    ids = json.loads(Path(QT_ELIGIBLE).read_text(encoding="utf-8")) if QT_ELIGIBLE else list(items)
    seq = sorted(ids)
    random.Random(QT_ORDER_SEED).shuffle(seq)
    item = items[seq[(day - QT_START).days % len(seq)]]
    m = re.match(r"^(.+?)\s+(\d+)[:：]", item["passageReference"])
    book, ch = m.group(1), m.group(2)
    verses, nums = [], []
    for v in item["verses"]:
        mv = re.search(r"(\d+)[:：](\d+)\s*$", v["reference"])
        c, n = (mv.group(1), mv.group(2)) if mv else (ch, re.search(r"(\d+)", v["reference"]).group(1))
        verses.append({"reference": f"{book} {c}:{n}", "text": v["text"].strip()})
        nums.append((int(c), int(n)))
    (c1, v1), (c2, v2) = nums[0], nums[-1]
    shown = (f"{book} {c1}:{v1}" if (c1, v1) == (c2, v2) else
             f"{book} {c1}:{v1}-{v2}" if c1 == c2 else f"{book} {c1}:{v1}-{c2}:{v2}")
    log(f"큐티 자료 #{item['id']} {shown} — {item['title'].strip()}")
    return {"id": item["id"], "title": item["title"].strip(), "passageReference": shown, "verses": verses,
            "summary": item.get("summary", ""), "sermon": item.get("sermon", ""),
            "meditation": item.get("meditation", ""),
            "application": [a for a in item.get("application", []) if a and a.strip()],
            "prayer": item.get("prayer", "")}


def make_script(lang: str, day: dt.date, out: Path) -> dict:
    if lang == "ko" and QT_DATA:
        qt = qt_from_data(day)
    else:
        qt = http_json(QT_URL, {"mode": "today", "language": lang})["qt"]
    verses = "\n".join(f"{v['reference']} {v['text']}" for v in qt["verses"])
    p = PROMPT[lang].format(title=qt["title"], ref=qt["passageReference"], verses=verses, summary=qt["summary"],
                            sermon=qt["sermon"], meditation=qt["meditation"], application=" ".join(qt["application"]))
    g = gemini_json(env()["GEMINI_API_KEY"], p)
    reading_intro = (f"오늘 주시는 말씀은 {speak_ref(qt['passageReference'], 'ko')} 말씀입니다."
                     if lang == "ko" else f"Hear the word of the Lord from {speak_ref(qt['passageReference'], 'en')}.")
    reading_end = "아멘. 하나님의 말씀입니다." if lang == "ko" else "This is the word of the Lord."
    songs = pick_songs(lang, day)
    parts = [
        {"id": "call", "title": "예배의 부름" if lang == "ko" else "Call to Worship",
         "text": OPENING[lang] + " " + clean_speech(g["call"])},
        {"id": "song1", "title": "찬양" if lang == "ko" else "Song of Praise", "song": songs[0]},
        {"id": "prayer", "title": "기도" if lang == "ko" else "Prayer", "text": clean_speech(g["prayer"])},
        {"id": "reading", "title": "성경 봉독" if lang == "ko" else "Scripture Reading",
         # 옛 성경체는 마침표가 없어 절마다 끊어 읽는다(글자는 그대로, 괄호 기호만 뺀다)
         "text": reading_intro + " " + ". ".join(clean_speech(v["text"]).rstrip(".") for v in qt["verses"])
                 + ". " + reading_end,
         "verbatim": True},
        {"id": "sermon", "title": qt["title"], "text": clean_speech(g["sermon"])},
        {"id": "closing", "title": "결단 기도" if lang == "ko" else "Closing Prayer",
         "text": clean_speech(qt["prayer"]) + " " + clean_speech(g["song2_intro"])},
        {"id": "song2", "title": "응답 찬양" if lang == "ko" else "Response Song", "song": songs[1]},
        {"id": "lords_prayer", "title": "주기도문" if lang == "ko" else "The Lord's Prayer",
         "text": FIXED[lang]["lords_prayer"], "fixed": True},
        {"id": "blessing", "title": "축복의 말씀" if lang == "ko" else "Words of Blessing",
         "text": FIXED[lang]["blessing"], "fixed": True},
    ]
    script = {"date": day.isoformat(), "lang": lang, "qt_id": qt.get("id"), "title": qt["title"], "passage": qt["passageReference"],
              "verses": qt["verses"], "parts": parts}
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(p.get("text", "")) for p in parts)
    log(f"원고 {n}자 · 찬양 {songs[0]['title']} / {songs[1]['title']}")
    return script


# 같은 원고 영어판(10-23 사용자: 하루에 한국어·영어 두 버전) — 설교·기도는 번역, 성경은 같은 구절 KJV 원문
BOOKS_EN = dict(zip(
    ("창세기 출애굽기 레위기 민수기 신명기 여호수아 사사기 룻기 사무엘상 사무엘하 열왕기상 열왕기하 역대상 역대하 에스라 느헤미야 "
     "에스더 욥기 시편 잠언 전도서 아가 이사야 예레미야 예레미야애가 에스겔 다니엘 호세아 요엘 아모스 오바댜 요나 미가 나훔 하박국 "
     "스바냐 학개 스가랴 말라기 마태복음 마가복음 누가복음 요한복음 사도행전 로마서 고린도전서 고린도후서 갈라디아서 에베소서 빌립보서 "
     "골로새서 데살로니가전서 데살로니가후서 디모데전서 디모데후서 디도서 빌레몬서 히브리서 야고보서 베드로전서 베드로후서 요한일서 "
     "요한이서 요한삼서 유다서 요한계시록").split(),
    ("Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|"
     "2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|"
     "Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|"
     "Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|"
     "2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|"
     "Revelation").split("|")))

TRANSLATE = """Translate this Korean worship script into natural, warm American English for spoken delivery by a calm pastor.
Keep the meaning and structure; do not add content. Write numbers as words; no brackets, quotation marks or emoji.
Do not quote Bible verses in any translation of your own beyond what the Korean text says.
Return one JSON object with exactly these keys: title, call, prayer, sermon, closing.

{body}"""


def kjv(ref_ko: str) -> tuple[str, list[dict]]:
    m = re.match(r"^(.*?)\s*(\d+):(\d+)(?:\s*[-~]\s*(\d+))?$", ref_ko.strip())
    book = BOOKS_EN[m.group(1).strip()]
    ref = f"{book} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
    d = http_json("https://bible-api.com/" + urllib.parse.quote(ref) + "?translation=kjv")
    return ref, [{"reference": f"{book} {v['chapter']}:{v['verse']}", "text": re.sub(r"\s+", " ", v["text"]).strip()}
                 for v in d["verses"]]


def make_script_en(ko: dict, day: dt.date, out: Path) -> dict:
    P = {p["id"]: p for p in ko["parts"]}
    strip_open = lambda t: t.replace(OPENING["ko"], "").strip()
    body = json.dumps({"title": ko["title"], "call": strip_open(P["call"]["text"]), "prayer": P["prayer"]["text"],
                       "sermon": P["sermon"]["text"], "closing": P["closing"]["text"]}, ensure_ascii=False)
    g = gemini_json(env()["GEMINI_API_KEY"], TRANSLATE.format(body=body))
    ref, verses = kjv(ko["passage"])
    songs = pick_songs("en", day)
    parts = [
        {"id": "call", "title": "Call to Worship", "text": OPENING["en"] + " " + clean_speech(g["call"])},
        {"id": "song1", "title": "Song of Praise", "song": songs[0]},
        {"id": "prayer", "title": "Prayer", "text": clean_speech(g["prayer"])},
        {"id": "reading", "title": "Scripture Reading", "verbatim": True,
         "text": f"Hear the word of the Lord from {speak_ref(ref, 'en')}. "
                 + " ".join(clean_speech(v["text"]) for v in verses) + " This is the word of the Lord."},
        {"id": "sermon", "title": clean_speech(g["title"]), "text": clean_speech(g["sermon"])},
        {"id": "closing", "title": "Closing Prayer", "text": clean_speech(g["closing"])},
        {"id": "song2", "title": "Response Song", "song": songs[1]},
        {"id": "lords_prayer", "title": "The Lord's Prayer", "text": FIXED["en"]["lords_prayer"], "fixed": True},
        {"id": "blessing", "title": "Words of Blessing", "text": FIXED["en"]["blessing"], "fixed": True},
    ]
    script = {"date": day.isoformat(), "lang": "en", "title": clean_speech(g["title"]), "passage": ref,
              "verses": verses, "parts": parts, "from": "ko"}
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"영어판 원고 {sum(len(p.get('text', '')) for p in parts)}자 · {ref} · 찬양 {songs[0]['title']} / {songs[1]['title']}")
    return script


# ── 2) 목소리 ─────────────────────────────────────────────────────────────
def chunks(text: str, lang: str) -> list[str]:
    """2~3문장씩 묶는다(문장마다 따로 만들면 매번 힘주어 시작해 구연동화처럼 들린다)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out, cur, lim = [], "", CHUNK_CHARS[lang]
    for s in sents:
        while len(s) > lim:                       # 아주 긴 문장은 쉼표에서 자른다
            cut = s.rfind(",", 0, lim)
            cut = cut if cut > lim // 3 else max(s.rfind(" ", 0, lim), lim // 3)   # 쉼표 없으면 띄어쓰기에서
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[: cut + 1].strip())
            s = s[cut + 1:].strip()
        if cur and len(cur) + 1 + len(s) > lim:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def norm_words(s: str, lang: str):
    return re.sub(r"[^가-힣]", "", s) if lang == "ko" else re.findall(r"[a-z]+", s.lower())


def err_rate(ref, hyp) -> float:
    d = list(range(len(hyp) + 1))
    for i, x in enumerate(ref, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(hyp, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[-1] / max(1, len(ref))


class Voice:
    def __init__(self, lang: str) -> None:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        from faster_whisper import WhisperModel
        torch.set_num_threads(THREADS)
        self.torch, self.lang = torch, lang
        self.ref = str(VOICE_DIR / REF[lang])
        t0 = time.time()
        self.tts = ChatterboxMultilingualTTS.from_pretrained(device=DEVICE)
        self.asr = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=THREADS)
        self.sr = self.tts.sr
        log(f"목소리 모델 준비 {time.time() - t0:.0f}초")

    def check(self, wav, text: str) -> float:
        import numpy as np
        import torchaudio.functional as F
        a = F.resample(wav, self.sr, 16000)[0].numpy().astype(np.float32)
        hyp = "".join(s.text for s in self.asr.transcribe(a, language=self.lang, beam_size=5)[0])
        return err_rate(norm_words(text, self.lang), norm_words(hyp, self.lang))

    def say(self, text: str):
        best = None
        for k in range(TRIES):
            self.torch.manual_seed(1000 + k)
            wav = self.tts.generate(text, language_id=self.lang, audio_prompt_path=self.ref,
                                    exaggeration=EXAGGERATION, cfg_weight=CFG)
            e = self.check(wav, text)
            if best is None or e < best[0]:
                best = (e, wav)
            if e <= MAX_ERR:
                break
        if best[0] > MAX_ERR:
            log(f"  [경고] 되읽기 오류 {best[0]:.0%} (가장 나은 것 사용): {text[:40]}…")
        return best

    def part(self, text: str, dst: Path) -> dict:
        import torchaudio
        pieces, errs, secs = [], [], []
        gap = self.torch.zeros(1, int(self.sr * 0.6))
        for c in chunks(text, self.lang):
            e, wav = self.say(c)
            pieces += [wav, gap]
            errs.append(e)
            secs.append(round((wav.shape[1] + gap.shape[1]) / self.sr, 3))   # 화면 자막 시간표용(늘리기 전 길이)
        out = self.torch.cat(pieces, dim=1)
        torchaudio.save(str(dst), out, self.sr)
        return {"sec": out.shape[1] / self.sr, "max_err": max(errs), "chunks": len(errs), "chunk_secs": secs}


def make_voice(script: dict, out: Path) -> None:
    lang = script["lang"]
    v = Voice(lang)
    CACHE.mkdir(parents=True, exist_ok=True)
    for p in script["parts"]:
        if "text" not in p:
            continue
        if p.get("fixed"):
            h = hashlib.sha1(f"{lang}|{REF[lang]}|{EXAGGERATION}|{CFG}|{p['text']}".encode()).hexdigest()[:12]
            dst = CACHE / f"{p['id']}_{lang}_{h}.wav"
            if dst.exists():
                p["audio"] = str(dst)
                log(f"{p['title']}: 저장된 음성 사용")
                continue
        else:
            dst = out / f"{p['id']}.wav"
        t0 = time.time()
        info = v.part(p["text"], dst)
        p["audio"], p["qc"] = str(dst), info
        log(f"{p['title']}: {info['sec']:.0f}초 · {time.time() - t0:.0f}초 걸림 · 최대 오류 {info['max_err']:.0%}")
        (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 3) 이어 붙이기 ────────────────────────────────────────────────────────
def download(url: str, dst: Path) -> Path:
    if not dst.exists():
        p = urllib.parse.urlsplit(url)
        url = p._replace(path=urllib.parse.quote(p.path)).geturl()
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
            dst.write_bytes(r.read())
    return dst


def dur(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def mix(script: dict, out: Path) -> Path:
    """순서대로 이어 붙이고 음량을 맞춘다. 20분을 넘으면 응답 찬양을 뺀다."""
    files = []
    for p in script["parts"]:
        if "song" in p:
            s = p["song"]
            p["audio"] = str(download(s["url"], CACHE / f"song_{s['slug'][:40]}_{s['n']:02d}.mp3"))
        files.append((p, Path(p["audio"])))
    total = sum(dur(f) / (1 if "song" in p else SPEED) for p, f in files) + 1.5 * len(files)
    if total > MAX_MIN * 60:
        files = [(p, f) for p, f in files if p["id"] != "song2"]
        log(f"20분 초과({total / 60:.1f}분) → 응답 찬양 뺌")
    t, timeline = 0.0, []
    inputs, filters = [], []
    for i, (p, f) in enumerate(files):
        inputs += ["-i", str(f)]
        slow = "song" not in p and SPEED != 1
        filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                       + (f"atempo={SPEED}," if slow else "")
                       + f"loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur=1.5[a{i}]")
        d = dur(f) / (SPEED if slow else 1) + 1.5
        timeline.append({"id": p["id"], "title": p["title"], "start": round(t, 1), "sec": round(d, 1),
                         **({"song": {k: p["song"][k] for k in ("title", "album", "youtube", "cover") if k in p["song"]}}
                            if "song" in p else {})})
        t += d
    concat = "".join(f"[a{i}]" for i in range(len(files))) + f"concat=n={len(files)}:v=0:a=1[out]"
    dst = out / f"worship_{script['date']}_{script['lang']}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters + [concat]),
                    "-map", "[out]", "-b:a", "160k", str(dst)], check=True)
    script["timeline"], script["total_sec"] = timeline, round(t, 1)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"완성 {dst.name} · {t / 60:.1f}분")
    for x in timeline:
        log(f"  {int(x['start'] // 60):02d}:{int(x['start'] % 60):02d}  {x['title']}")
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["ko", "en"], required=True)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--voice", action="store_true", help="낭독 음성 만들기(Chatterbox)")
    ap.add_argument("--mix", action="store_true", help="찬양과 이어 붙여 mp3")
    a = ap.parse_args()
    day = dt.date.fromisoformat(a.date)
    out = OUT / f"{a.date}_{a.lang}"
    sp = out / "script.json"
    ko_sp = OUT / f"{a.date}_ko" / "script.json"
    if sp.exists():
        script = json.loads(sp.read_text(encoding="utf-8"))
    elif a.lang == "en" and ko_sp.exists():          # 같은 원고 영어판
        script = make_script_en(json.loads(ko_sp.read_text(encoding="utf-8")), day, out)
    else:
        script = make_script(a.lang, day, out)
    if a.voice:
        make_voice(script, out)
    if a.mix:
        mix(script, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

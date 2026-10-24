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
MUSIC_DIR = Path(os.environ.get("WORSHIP_MUSIC_DIR", OUT.parent / "music"))   # 직접 연주·자작 곡 폴더(맥미니 ~/Work/nexis-worship/music)
VOICE_DIR = Path(os.environ.get("WORSHIP_REF_DIR", r"D:\YH\voice-lab\ref"))   # 사용자 녹음(레포 밖, 비공개)
THREADS = int(os.environ.get("WORSHIP_THREADS", "8"))   # 미니PC 는 3 (다른 서비스 몫을 남긴다)
DEVICE = os.environ.get("WORSHIP_DEVICE", "cpu")   # 맥미니 = mps(Apple GPU). Whisper 는 MPS 미지원이라 늘 CPU
REF = {"ko": os.environ.get("WORSHIP_REF_KO", "my_ko2.wav"),   # 한국어 = 처음 확정 '억양 3'(10-23). 10-24 B 확정(E=my_ko4 는 '칙' 잦음)
       "en": os.environ.get("WORSHIP_REF_EN", "my_en.wav")}    # 다른 사람 목소리는 docs/voice-onboarding.md — 파일만 바꿔 끼운다
QT_URL = "https://qt.yojosuknam.com/api/generate-qt"
# 한국어 원고의 바탕 = 말씀Log 큐티 2,000개(autovid data/qt_data.json) 중 개역한글 검증 항목(qt-insta eligible_ids).
# qt-insta 와 같은 순서표라 같은 날 인스타 카드와 같은 본문이 된다(10-23 사용자). 파일이 없으면 위 API.
QT_DATA = os.environ.get("WORSHIP_QT_DATA", "")
QT_ELIGIBLE = os.environ.get("WORSHIP_QT_ELIGIBLE", "")
QT_START, QT_ORDER_SEED = dt.date(2026, 9, 15), "malsseumlog-insta-v1"   # qt_insta.py 의 START·ORDER_SEED 와 같아야 함
RADIO_JSON = "https://music.yojosuknam.com/album/radio.json"
TEXT_MODEL = "gemini-3.1-pro-preview"   # 2.5-pro 는 신규 사용 불가(10-22 404)
MAX_MIN = 25.0   # 기도회(약 3~4분)가 들어가 20 → 25분(10-24). 넘으면 응답 찬양을 뺀다
UA = "Mozilla/5.0 NexisWorship/1.0"

# 억양: '구연동화 같다'(10-22) → 감정 강도를 낮춘다.
# '쉼 없이 빠르다'(10-23) → 한 문장씩 만들고 문장 사이 0.8초 쉼, cfg 0.4(서두르지 않게) — 비교 샘플 '내목소리_천천히' 방식
EXAGGERATION, CFG = 0.25, 0.4
# 조사(docs/research/2026-10-24_내목소리-TTS-자연스럽게.md) 탐색 시작값 — 10-24 비교 샘플 ③ 사용자 확정 → 기본 켬(0 이면 옛 값)
TUNE = os.environ.get("WORSHIP_TUNE", "1") == "1"
if TUNE:
    EXAGGERATION, CFG = 0.20, 0.35
GEN_KW = {"temperature": 0.75, "repetition_penalty": 1.2, "min_p": 0.05} if TUNE else {}   # 1.2 = chatterbox master 기본값
MPS_LIMIT_GB = float(os.environ.get("WORSHIP_MPS_LIMIT_GB", "9"))   # 넘으면 저장해 둔 문장부터 프로세스를 새로 띄워 이어 만든다
GAP = 0.8               # 문장 사이 쉼(초) — 고정 방식
# '더 자연스럽게'(10-24, 무료 범위) — WORSHIP_NATURAL=1 일 때: 문장부호별 쉼(물음표는 생각할 틈),
# 엔진이 문장 앞뒤에 들쭉날쭉 남기는 무음을 다듬고, 아주 짧은 문장('사랑하는 여러분.')은 다음 문장과 함께 만든다
NATURAL = os.environ.get("WORSHIP_NATURAL", "1") == "1"   # 10-24 사용자 B 확정 → 기본 켬(0 이면 옛 고정 쉼)
# 완성 음성에서 들리는 '총' 쉼(초, trim 이 남긴 앞뒤 여백 포함) — 10-24 조사: 물음표를 기능별로 나눈다.
# 생각을 청하는 질문은 길게, 바로 답·다음 질문이 이어지면 짧게. 마침표는 B 확정 때 들은 0.8초 그대로
PAUSE = {".": 0.80, "!": 0.80, ",": 0.30, "?think": 1.00, "?ans": 0.60}
EDGE = 0.03 + 0.06   # trim 이 남기는 앞 30ms·뒤 60ms
ANSWER_START = ("그것은", "그건", "바로", "왜냐하면", "그렇습니다", "아닙니다", "네,", "네.", "아니요", "답은", "그 이유는")
PARA = os.environ.get("WORSHIP_CHUNK", "") == "para"   # 비교 시험: 1~3문장 의미 묶음(110자 이내, 질문에서 끊음)
SHORT = {"ko": 12, "en": 25}   # 이보다 짧은 문장은 다음 문장과 붙인다
CHUNK_CHARS = {"ko": 60, "en": 130}   # 이보다 긴 문장은 쉼표·절 끝에서 나눈다(길면 엔진이 갑자기 빨라진다, 10-24)
CLAUSE_END = tuple("고 며 서 니 면 지 도 만 데 라 요".split())
# 기도회 인도는 원고를 처음부터 짧은 문장으로 쓰고(프롬프트) 원고의 쉼표·마침표에서만 넉넉히 쉰다.
# 마디를 억지로 잘라 쉼표를 붙였더니 '어떤 상황에서도, / 그리고,'처럼 쉼 자리가 어색했다(10-24 사용자) → 자르지 않는다.
PM_PAUSE = {",": 0.45, ".": 1.00, "!": 1.00}   # 쉼표 없을 때 끊어도 자연스러운 어절 끝(1분 묵상 _breathe 참고)
# 엔진이 잘못 읽는 말 — 낭독에 넣는 글만 바꾸고 자막은 그대로(10-24 '말씀으그'·'아이' 지적). 긴 것부터 바꾼다
SPEAK_KO = {"말씀 Log": "말씀로그", "말씀Log": "말씀로그", "Log": "로그", "AI": "에이아이", "QT": "큐티"}
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
    if n >= 10000:                                   # 만 단위(연도·큰 수)
        q, n = divmod(n, 10000)
        return ("" if q == 1 else sino(q)) + "만" + (sino(n) if n else "")
    out = ""
    for unit, name in ((1000, "천"), (100, "백"), (10, "십")):
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


def display_ref(text: str, lang: str) -> str:
    """자막용 — speak_ref 로 풀어 쓴 장·절을 숫자로 되돌린다(10-24 '민수기이십육장' 자막 지적).
    '민수기 육장 이십사절에서 이십육절' → '민수기 6장 24절에서 26절' / 'chapter six, verses twenty-four to twenty-six' → '6:24-26'"""
    if lang == "ko":
        nums = {sino(n): n for n in range(1, 200)}
        alt = "|".join(sorted(nums, key=len, reverse=True))
        text = re.sub(rf"({alt})장 ({alt})절(?:에서 ({alt})절)?",
                      lambda m: f"{nums[m[1]]}장 {nums[m[2]]}절" + (f"에서 {nums[m[3]]}절" if m[3] else ""), text)
        books = "|".join(sorted(BOOKS_EN, key=len, reverse=True))   # 책 이름 뒤 '육장'·'이십삼편'(시편)만
        return re.sub(rf"({books}) ({alt})(장|편)", lambda m: f"{m[1]} {nums[m[2]]}{m[3]}", text)
    nums = {en_num(n): n for n in range(1, 200)}
    alt = "|".join(sorted(map(re.escape, nums), key=len, reverse=True))
    return re.sub(rf"\bchapter ({alt}), verses? ({alt})(?: to ({alt}))?",
                  lambda m: f"{nums[m[1]]}:{nums[m[2]]}" + (f"-{nums[m[3]]}" if m[3] else ""), text)


# ── 1) 원고 ───────────────────────────────────────────────────────────────
PROMPT = {
    "ko": """당신은 작은 교회의 따뜻하고 담백한 목회자입니다. 아래 오늘의 큐티 자료로, 라디오처럼 혼자 듣는 사람을 위한
20분 말씀 묵상 예배의 낭독 원고를 씁니다. 반드시 JSON 하나만 출력하세요.

{{"call": "예배의 부름 — 3~4문장. 듣는 이를 예배로 초대하고 마지막 문장은 찬양으로 마음을 열자는 말",
  "prayer": "여는 기도 — 350~450자. 감사·고백·말씀을 사모하는 마음, '예수님의 이름으로 기도합니다. 아멘.'으로 끝",
  "sermon": "말씀 — 2,000~2,300자. 도입 → 세 가지 요점 → 맺음. 오늘 본문 구절만 인용",
  "song2_intro": "결단 기도 뒤 응답 찬양으로 넘어가는 한 문장",
  "prayer_meeting": {{"intro": "기도회로 초대하는 1~2문장 — 함께 마음을 모아 기도하자는 말",
                      "topics": ["'첫째,'로 시작하는 짧은 인도 3문장 — 오늘 말씀을 삶에서 살아 내도록. 마지막은 '…을 위해 기도합시다.'",
                                 "'둘째,'로 시작하는 짧은 인도 3문장 — 가정과 이웃, 아프고 지친 이들. 마지막은 '…을 위해 기도합시다.'",
                                 "'셋째,'로 시작하는 짧은 인도 3문장 — 교회와 나라, 세상. 마지막은 '…을 위해 기도합시다.'"],
                      "close": "기도회를 맺고 '이어서 주님 가르쳐 주신 기도로 함께 기도하겠습니다'로 넘어가는 한 문장"}}}}

기도회 인도 문장은 회중에게 기도 제목을 알려 주는 말입니다. '…하옵소서'처럼 기도문 자체를 쓰지 마세요.
기도회 문장은 특히 짧게 — 한 문장 15~30자, 소리 내어 천천히 읽기 좋은 말로. 쉼표는 말하다 실제로 숨을 쉬는 자리에만(한 문장에 많아야 하나).
  예) "첫째, 오늘 말씀을 붙들고 기도합시다. 어떤 형편에서도 기뻐하고 감사하도록. 주님 뜻대로 사는 하루를 위해 기도합시다."
기도회 뒤에 주기도문과 축복의 말씀이 이어지므로 '예배를 마칩니다'라고 쓰지 마세요.

규칙:
- 소리 내어 읽을 글입니다. 괄호·따옴표·번호표·'첫째:' 같은 표기·이모지를 쓰지 말고 말로 풀어 쓰세요.
- 숫자는 아라비아 숫자를 쓰지 말고 한글로 쓰세요. 성경 장절 표기(4:13 등)는 쓰지 마세요.
- 오늘 본문 말고 다른 성경 구절을 직접 인용하지 마세요(틀린 인용 방지).
- 과장된 감탄, 설교 상투어 반복, 특정 교단·정치·헌금 이야기를 피하세요. 담담하고 따뜻하게.
- 문장은 짧게(한 문장 40자 안팎, 길어도 60자를 넘기지 마세요 — 긴 문장은 낭독이 갑자기 빨라집니다).

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
  "song2_intro": "one sentence leading from the closing prayer into a response song",
  "prayer_meeting": {{"intro": "1 to 2 sentences inviting everyone into a time of prayer together",
                      "topics": ["starts with 'First,' and ends with 'Let us pray for …' — 3 short sentences: living out today's word",
                                 "starts with 'Second,' and ends with 'Let us pray for …' — 3 short sentences: families, neighbors, the sick and weary",
                                 "starts with 'Third,' and ends with 'Let us pray for …' — 3 short sentences: the church, the nation and the world"],
                      "close": "one sentence closing the prayer time and leading into the Lord's Prayer"}}}}

The prayer-time lines guide the listeners on what to pray for; do not write the prayer itself.
Keep prayer-time sentences short (5 to 12 words) and easy to read aloud slowly; use a comma only where a speaker would breathe.
The Lord's Prayer and a blessing follow, so do not say the service is ending.

Rules:
- This will be read aloud. No brackets, quotation marks, bullet labels like 'First:', or emoji; write it as speech.
- Write numbers as words. Do not write chapter:verse notation.
- Do not quote any Bible verse other than today's passage (to avoid misquotes).
- Avoid exaggerated exclamations, cliches, denominational, political or offering talk. Calm and warm.
- Keep sentences short (about 15 words, never more than 25).

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
    g = json.loads(d["candidates"][0]["content"]["parts"][0]["text"])
    return g[0] if isinstance(g, list) and g and isinstance(g[0], dict) else g   # 가끔 [{...}] 로 감싸서 준다(10-23)


def clean_speech(s: str) -> str:
    s = re.sub(r"[\"'“”‘’()\[\]*#]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def pick_songs(lang: str, day: dt.date) -> dict:
    """예배 자리별 곡 — music.json 대장에서 권리 확인(verified)된 곡만(docs/worship-order.md).
    open = 함께 부르는 찬송(저작권 만료 곡 직접 반주 → 자작 찬송가 → 없으면 CCM), response = 응답 찬양(자작 찬송가·CCM),
    prayer = 기도회 배경 연주곡."""
    import music_library as ml
    o = day.toordinal()
    first = ml.pick("open", lang, o)
    resp = ml.pick("response", lang, o, {first["id"]})
    twin = next((x for x in ml.load() if x["id"] == resp.get("instrumental")
                 and x.get("license", {}).get("status") == "verified"), None)   # 응답 찬송의 연주판이 있으면 기도회 배경으로
    return {"open": first, "response": resp, "prayer": dict(twin) if twin else ml.pick("prayer", lang, o)}


SONG_TITLE = {"hymn_pd": ("함께 찬송", "Hymn"), "hymn_own": ("찬송", "Hymn"), "ccm": ("찬양", "Song of Praise")}
PRAY_SEC = float(os.environ.get("WORSHIP_PRAY_SEC", "40"))   # 기도회 제목마다 함께 기도하는 시간(초)
# 기도회 인도는 다른 낭독(8%)보다 더 천천히 — 10-25 실측 6.7음절/초로 설교(5.7)보다 17% 빨랐다(10-24 사용자 '말이 너무 빠르다')
PM_SPEED = float(os.environ.get("WORSHIP_PM_SPEED", "0.85"))


def song_title(song: dict, lang: str, response: bool = False) -> str:
    if response:
        return "응답 찬양" if lang == "ko" else "Response Song"
    return SONG_TITLE.get(song.get("type", "ccm"), SONG_TITLE["ccm"])[0 if lang == "ko" else 1]


def pm_part(lang: str, pm: dict, bed: dict) -> dict:
    """기도회 — 운영자 목소리로 '첫째, …를 위해 기도합시다' 인도 → 연주곡 위에서 PRAY_SEC 초 함께 기도(×3)."""
    return {"id": "prayer_meeting", "title": "기도회" if lang == "ko" else "Prayer Time", "music": bed,
            "pm": {"intro": clean_speech(pm["intro"]), "topics": [clean_speech(t) for t in pm["topics"]][:3],
                   "close": clean_speech(pm["close"])}}


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
        {"id": "song1", "title": song_title(songs["open"], lang), "song": songs["open"]},
        {"id": "prayer", "title": "기도" if lang == "ko" else "Prayer", "text": clean_speech(g["prayer"])},
        {"id": "reading", "title": "성경 봉독" if lang == "ko" else "Scripture Reading",
         # 옛 성경체는 마침표가 없어 절마다 끊어 읽는다(글자는 그대로, 괄호 기호만 뺀다)
         "text": reading_intro + " " + ". ".join(clean_speech(v["text"]).rstrip(".") for v in qt["verses"])
                 + ". " + reading_end,
         "verbatim": True},
        {"id": "sermon", "title": qt["title"], "text": clean_speech(g["sermon"])},
        {"id": "closing", "title": "결단 기도" if lang == "ko" else "Closing Prayer",
         "text": clean_speech(qt["prayer"]) + " " + clean_speech(g["song2_intro"])},
        {"id": "song2", "title": song_title(songs["response"], lang, True), "song": songs["response"]},
        pm_part(lang, g["prayer_meeting"], songs["prayer"]),
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
    log(f"원고 {n}자 · 찬송 {songs['open']['title']}({songs['open']['type']}) / 응답 {songs['response']['title']}"
        f"({songs['response']['type']}) / 기도회 배경 {songs['prayer']['title']}")
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
Return one JSON object with exactly these keys: title, call, prayer, sermon, closing, pm_intro, pm_topics, pm_close.
pm_topics is an array of three strings that start with "First,", "Second," and "Third,".

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
                       "sermon": P["sermon"]["text"], "closing": P["closing"]["text"],
                       "pm_intro": P["prayer_meeting"]["pm"]["intro"], "pm_topics": P["prayer_meeting"]["pm"]["topics"],
                       "pm_close": P["prayer_meeting"]["pm"]["close"]}, ensure_ascii=False)
    g = gemini_json(env()["GEMINI_API_KEY"], TRANSLATE.format(body=body))
    ref, verses = kjv(ko["passage"])
    songs = pick_songs("en", day)
    parts = [
        {"id": "call", "title": "Call to Worship", "text": OPENING["en"] + " " + clean_speech(g["call"])},
        {"id": "song1", "title": song_title(songs["open"], "en"), "song": songs["open"]},
        {"id": "prayer", "title": "Prayer", "text": clean_speech(g["prayer"])},
        {"id": "reading", "title": "Scripture Reading", "verbatim": True,
         "text": f"Hear the word of the Lord from {speak_ref(ref, 'en')}. "
                 + " ".join(clean_speech(v["text"]) for v in verses) + " This is the word of the Lord."},
        {"id": "sermon", "title": clean_speech(g["title"]), "text": clean_speech(g["sermon"])},
        {"id": "closing", "title": "Closing Prayer", "text": clean_speech(g["closing"])},
        {"id": "song2", "title": "Response Song", "song": songs["response"]},
        pm_part("en", {"intro": g["pm_intro"], "topics": g["pm_topics"], "close": g["pm_close"]}, songs["prayer"]),
        {"id": "lords_prayer", "title": "The Lord's Prayer", "text": FIXED["en"]["lords_prayer"], "fixed": True},
        {"id": "blessing", "title": "Words of Blessing", "text": FIXED["en"]["blessing"], "fixed": True},
    ]
    script = {"date": day.isoformat(), "lang": "en", "title": clean_speech(g["title"]), "passage": ref,
              "verses": verses, "parts": parts, "from": "ko"}
    out.mkdir(parents=True, exist_ok=True)
    (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"영어판 원고 {sum(len(p.get('text', '')) for p in parts)}자 · {ref} · 찬송 {songs['open']['title']} / 응답 {songs['response']['title']}"
        f" / 기도회 배경 {songs['prayer']['title']}")
    return script


# ── 2) 목소리 ─────────────────────────────────────────────────────────────
def chunks(text: str, lang: str, pm: bool = False) -> list[str]:
    """한 문장씩(10-23 '쉼 없이 빠르다' — 묶으면 엔진이 문장 사이를 쉬지 않고 이어 읽는다). 사이 쉼은 GAP.
    pm=True(기도회 인도)는 원고의 쉼표에서도 끊어 PM_PAUSE 만큼 쉰다(문장 안 마디를 따로 읽어 몰아 읽지 않게)."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out, lim = [], CHUNK_CHARS[lang]
    for s in sents:
        if pm:
            out += [x.strip() for x in re.split(r"(?<=,)\s+", s) if x.strip()]
            continue
        while len(s) > lim:                       # 긴 문장은 쉼표에서, 없으면 절 끝(…고·…며·…서) 띄어쓰기에서 자른다
            cut = s.rfind(",", lim // 3, lim)
            if cut > 0:
                out.append(s[: cut + 1].strip())
                s = s[cut + 1:].strip()
                continue
            sp = [i for i in range(lim // 3, min(lim, len(s))) if s[i] == " " and s[i - 1] in CLAUSE_END]
            cut = sp[-1] if sp else max(s.rfind(" ", 0, lim), lim // 3)
            out.append(s[:cut].strip() + ",")      # 쉼표를 붙여 짧게 쉬게(PAUSE[','])
            s = s[cut:].strip()
        if s:
            out.append(s)
    if NATURAL:
        merged = []
        for s in out:
            if merged and len(merged[-1]) < SHORT[lang] and len(merged[-1]) + 1 + len(s) <= lim:
                merged[-1] = f"{merged[-1]} {s}"
            else:
                merged.append(s)
        out = merged
    if PARA:                                       # 1~3문장씩 묶되 110자·질문에서 끊는다
        grouped, n = [], 0
        for s in out:
            if grouped and n < 3 and not grouped[-1].endswith("?") and len(grouped[-1]) + 1 + len(s) <= 110:
                grouped[-1], n = f"{grouped[-1]} {s}", n + 1
            else:
                grouped.append(s)
                n = 1
        out = grouped
    return out


def pause_after(chunk: str, nxt: str | None, pm: bool = False) -> float:
    """이 묶음 뒤에 넣을 무음(초) = PAUSE 총 쉼 − trim 여백. 고정 방식이면 GAP."""
    if not NATURAL:
        return GAP
    end = chunk.rstrip()[-1:]
    if end == "?":
        key = "?ans" if nxt and (nxt.rstrip().endswith("?") or nxt.lstrip().startswith(ANSWER_START)) else "?think"
    else:
        key = end if end in PAUSE else "."
    return max(0.1, (PM_PAUSE if pm and key in PM_PAUSE else PAUSE)[key] - EDGE)


NATIVE_TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
NATIVE_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
COUNTERS = "시간|명|개|사람|살|권|마리|가지|번|잔|송이|분께|군데|달|주일"


def native(n: int) -> str:
    """고유어 수(단위 앞): 3명 → 세 명, 20살 → 스무 살. 100 이상은 한자어."""
    if not 0 < n < 100:
        return sino(n)
    t, o = divmod(n, 10)
    return "스무" if n == 20 else NATIVE_TENS[t] + NATIVE_ONES[o]


def normalize_ko(text: str) -> str:
    """낭독용 숫자 읽기(10-24 조사 표 기준) — 성경 장절 → 날짜·시각 → 개수 → 퍼센트 → 남은 숫자. 자막에는 쓰지 않는다."""
    books = "|".join(sorted(BOOKS_EN, key=len, reverse=True))
    t = re.sub(rf"({books})\s*(\d+)\s*[:：]\s*(\d+)(?:\s*[-–~∼]\s*(\d+))?",
               lambda m: speak_ref(f"{m[1]} {m[2]}:{m[3]}" + (f"-{m[4]}" if m[4] else ""), "ko"), text)
    t = re.sub(rf"({books})\s*(\d+)\s*(장|편)", lambda m: f"{m[1]} {sino(int(m[2]))}{m[3]}", t)
    t = re.sub(r"(\d+)\s*년", lambda m: f"{sino(int(m[1]))} 년", t)
    t = re.sub(r"(\d+)\s*월", lambda m: {6: "유월", 10: "시월"}.get(int(m[1]), f"{sino(int(m[1]))}월"), t)
    t = re.sub(r"(\d+)\s*일(?![가-힣])", lambda m: f"{sino(int(m[1]))} 일", t)
    t = re.sub(rf"(\d+)\s*({COUNTERS})", lambda m: f"{native(int(m[1]))} {m[2]}", t)   # '3시간'을 '시' 앞에서 먼저
    t = re.sub(r"(\d+)\s*시(?![작간])", lambda m: f"{native(int(m[1]))} 시", t)
    t = re.sub(r"(\d+)\s*분", lambda m: f"{sino(int(m[1]))} 분", t)
    t = re.sub(r"(\d+)(?:\.(\d+))?\s*%",
               lambda m: sino(int(m[1])) + (" 점 " + " ".join(sino(int(d)) for d in m[2]) if m[2] else "") + " 퍼센트", t)
    return re.sub(r"\d+", lambda m: sino(int(m[0])), t)


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
        # 참조 녹음 분석은 한 번만 — 문장마다 audio_prompt_path 로 다시 분석하면 MPS 메모리가 쌓여 14~26GB 까지 컸다(10-24)
        self.tts.prepare_conditionals(self.ref, exaggeration=EXAGGERATION)
        self.asr = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=THREADS)
        self.sr = self.tts.sr
        log(f"목소리 모델 준비 {time.time() - t0:.0f}초")

    def check(self, wav, text: str) -> float:
        import numpy as np
        import torchaudio.functional as F
        a = F.resample(wav, self.sr, 16000)[0].numpy().astype(np.float32)
        hyp = "".join(s.text for s in self.asr.transcribe(a, language=self.lang, beam_size=5)[0])
        if self.lang == "ko":                     # Whisper 는 '6장'처럼 숫자로 적는다 → 낭독문과 같은 방식으로 맞춰 비교
            hyp = normalize_ko(hyp)
        return err_rate(norm_words(text, self.lang), norm_words(hyp, self.lang))

    def say(self, text: str):
        import gc
        speak = text
        if self.lang == "ko":                     # 엔진이 잘못 읽는 말·숫자만 바꿔 넣는다(자막은 text 그대로)
            for k_, v_ in SPEAK_KO.items():
                speak = speak.replace(k_, v_)
            speak = normalize_ko(speak)
        best = None
        for k in range(TRIES):
            self.torch.manual_seed(1000 + k)
            with self.torch.inference_mode():
                out = self.tts.generate(speak, language_id=self.lang, exaggeration=EXAGGERATION, cfg_weight=CFG,
                                        **GEN_KW)
            wav = out.detach().to("cpu").contiguous()   # GPU 에 결과를 쌓지 않는다(10-24 조사: CPU 로 옮겨 보관)
            del out
            gc.collect()
            if DEVICE == "mps":
                self.torch.mps.synchronize()
                self.torch.mps.empty_cache()
            e = self.check(wav, speak)
            if best is None or e < best[0]:
                best = (e, wav)
            if e <= MAX_ERR:                      # '칙' 때문엔 다시 만들지 않는다(B 목소리엔 없음, 10-24 사용자)
                break
        if best[0] > MAX_ERR:
            log(f"  [경고] 되읽기 오류 {best[0]:.0%} (가장 나은 것 사용): {text[:40]}…")
        return best

    def mps_gb(self) -> float:
        return self.torch.mps.driver_allocated_memory() / 2 ** 30 if DEVICE == "mps" else 0.0

    def restart_if_heavy(self) -> None:
        """GPU 메모리가 MPS_LIMIT_GB 를 넘으면 같은 명령으로 프로세스를 새로 띄운다 — 문장 저장본(_chunks)부터 이어 만든다."""
        gb = self.mps_gb()
        if gb <= MPS_LIMIT_GB:
            return
        n = int(os.environ.get("WORSHIP_RESTARTS", "0")) + 1
        if n > 40:
            raise RuntimeError(f"GPU 메모리 {gb:.1f}GB — 다시 띄우기 {n - 1}번 넘음")
        log(f"  GPU 메모리 {gb:.1f}GB > {MPS_LIMIT_GB:g}GB → 저장한 데서 이어 만들도록 다시 띄움({n}번째)")
        os.environ["WORSHIP_RESTARTS"] = str(n)
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def fade(self, wav):
        """문장 앞뒤 20·30ms 페이드 — 문장 경계의 '틱' 방지."""
        n_in, n_out = int(self.sr * 0.02), int(self.sr * 0.03)
        if wav.shape[1] > n_in + n_out:
            wav = wav.clone()
            wav[0, :n_in] *= self.torch.linspace(0, 1, n_in)
            wav[0, -n_out:] *= self.torch.linspace(1, 0, n_out)
        return wav

    def trim(self, wav):
        """문장 앞뒤에 엔진이 남긴 무음을 다듬는다(앞 30ms·뒤 60ms 여유) — 쉼을 PAUSE 대로 고르게."""
        x = wav[0].abs()
        idx = (x > max(0.01, float(x.max()) * 0.02)).nonzero()
        if len(idx) == 0:
            return wav
        a = max(0, int(idx[0]) - int(self.sr * 0.03))
        b = min(x.shape[0], int(idx[-1]) + int(self.sr * 0.06))
        return wav[:, a:b]

    def part(self, text: str, dst: Path, pm: bool = False) -> dict:
        import torchaudio
        pieces, errs, secs = [], [], []
        ck = dst.parent / "_chunks"               # 문장 저장본 — 중간에 멈추거나 다시 띄워도 여기부터 이어 만든다
        ck.mkdir(parents=True, exist_ok=True)
        cs = chunks(text, self.lang, pm)
        for i, c in enumerate(cs):
            key = hashlib.sha1(f"{self.lang}|{REF[self.lang]}|{EXAGGERATION}|{CFG}|{GEN_KW}|{NATURAL}|n1|{c}"
                               .encode()).hexdigest()[:16]
            f, meta = ck / f"{key}.wav", ck / f"{key}.json"
            if f.exists() and meta.exists():
                wav, _ = torchaudio.load(str(f))
                e = json.loads(meta.read_text(encoding="utf-8"))["err"]
            else:
                e, wav = self.say(c)
                wav = self.fade(self.trim(wav) if NATURAL else wav)
                torchaudio.save(str(f), wav, self.sr)
                meta.write_text(json.dumps({"err": e, "text": c}, ensure_ascii=False), encoding="utf-8")
                self.restart_if_heavy()
            gap = self.torch.zeros(1, int(self.sr * pause_after(c, cs[i + 1] if i + 1 < len(cs) else None, pm)))
            pieces += [wav, gap]
            errs.append(e)
            secs.append(round((wav.shape[1] + gap.shape[1]) / self.sr, 3))   # 화면 자막 시간표용(늘리기 전 길이)
        out = self.torch.cat(pieces, dim=1)
        torchaudio.save(str(dst), out, self.sr)
        return {"sec": out.shape[1] / self.sr, "max_err": max(errs), "chunks": len(errs), "chunk_secs": secs,
                "gpu_gb": round(self.mps_gb(), 1)}


def make_voice(script: dict, out: Path) -> None:
    lang = script["lang"]
    v = Voice(lang)
    CACHE.mkdir(parents=True, exist_ok=True)
    for p in script["parts"]:
        if "pm" in p:                             # 기도회 인도 — 여는 말·제목 셋·맺는 말을 따로 만든다(사이에 함께 기도하는 시간)
            t0, pa = time.time(), {}
            items = [("intro", p["pm"]["intro"])] + [(f"topic{i + 1}", x) for i, x in enumerate(p["pm"]["topics"])] \
                + [("close", p["pm"]["close"])]
            for k, txt in items:
                dst = out / f"pm_{k}.wav"
                pa[k] = {"audio": str(dst), "qc": v.part(txt, dst, pm=True)}
            p["pm_audio"] = pa
            log(f"{p['title']}: 인도 {len(items)}마디 · {time.time() - t0:.0f}초 걸림 · 최대 오류 "
                f"{max(x['qc']['max_err'] for x in pa.values()):.0%}")
            (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
            continue
        if "text" not in p:
            continue
        if p.get("fixed"):
            h = hashlib.sha1(f"{lang}|{REF[lang]}|{EXAGGERATION}|{CFG}|{GAP}|clk|{'nat' if NATURAL else ''}|sp1|{p['text']}".encode()).hexdigest()[:12]
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
        log(f"{p['title']}: {info['sec']:.0f}초 · {time.time() - t0:.0f}초 걸림 · 최대 오류 {info['max_err']:.0%}"
            f" · GPU {info['gpu_gb']}GB")
        (out / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")


# ── 3) 이어 붙이기 ────────────────────────────────────────────────────────
def download(url: str, dst: Path) -> Path:
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)   # 미니PC 조립은 목소리를 안 만들어 cache/ 가 없다
        p = urllib.parse.urlsplit(url)
        url = p._replace(path=urllib.parse.quote(p.path)).geturl()
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
            dst.write_bytes(r.read())
    return dst


def dur(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def loudness(f: Path) -> float:
    """통합 음량(LUFS) 측정 — ffmpeg loudnorm 1차 측정값."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(f), "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r'"input_i"\s*:\s*"(-?[\d.]+|-inf)"', r.stderr)
    return float(m.group(1)) if m and m.group(1) != "-inf" else -16.0


def song_audio(s: dict) -> Path:
    """대장의 곡 → 음원 파일. 채널 곡은 내려받아 cache/, 직접 연주·자작 곡은 MUSIC_DIR/<폴더>/<파일>."""
    if s.get("source") == "local":
        return MUSIC_DIR / s["folder"] / s["file"]
    return download(s["url"], CACHE / f"song_{s['slug'][:40]}_{int(s['n']):02d}.mp3")


def build_prayer_meeting(p: dict, out: Path) -> Path:
    """기도회 한 덩어리 — 인도 목소리(여는 말 → 제목마다 인도 + PRAY_SEC 초 함께 기도 → 맺는 말)를
    연주곡 위에 얹는다. 말할 때는 연주가 저절로 낮아진다(sidechaincompress). 화면용 시각표는 p['pm_marks']."""
    pa = p["pm_audio"]
    order = ["intro"] + [f"topic{i + 1}" for i in range(len(p["pm"]["topics"]))] + ["close"]
    inputs, filt, marks, t = [], [], [], 0.0
    for i, k in enumerate(order):
        f = Path(pa[k]["audio"])
        body = dur(f) / PM_SPEED
        gain = max(-20.0, min(20.0, -16.0 - loudness(f)))
        pad = PRAY_SEC if k.startswith("topic") else (2.0 if k == "intro" else 0.0)
        inputs += ["-i", str(f)]
        filt.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,adeclick,atempo={PM_SPEED},"
                    f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=disabled,"
                    f"afade=t=in:d=0.02,afade=t=out:st={max(0.0, body - 0.02):.3f}:d=0.02,apad=pad_dur={pad}[v{i}]")
        marks.append({"k": k, "start": round(t, 2), "speak_end": round(t + body, 2), "end": round(t + body + pad, 2)})
        t += body + pad
    total = t + 3.0
    bed = song_audio(p["music"])
    bgain = max(-30.0, min(10.0, -27.0 - loudness(bed)))          # 배경은 낭독(-16)보다 약 11LU 작게
    inputs += ["-stream_loop", "-1", "-i", str(bed)]
    n = len(order)
    filt += ["".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,apad=pad_dur=3[voice]",
             "[voice]asplit[vs][vm]",
             f"[{n}:a]aresample=44100,aformat=channel_layouts=stereo,volume={bgain:.2f}dB,atrim=duration={total:.2f},"
             f"afade=t=in:d=2.5,afade=t=out:st={max(0.0, total - 4):.2f}:d=4[bed]",
             "[bed][vs]sidechaincompress=threshold=0.02:ratio=6:attack=40:release=900[duck]",
             "[duck][vm]amix=inputs=2:duration=longest:normalize=0[out]"]
    dst = out / "prayer_meeting.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-t", f"{total:.2f}", str(dst)], check=True)
    p["audio"], p["pm_marks"], p["pm_speed"] = str(dst), marks, PM_SPEED   # 화면은 이 속도로 문장 시각을 맞춘다
    return dst


def mix(script: dict, out: Path) -> Path:
    """순서대로 이어 붙이고 음량을 맞춘다. 20분을 넘으면 응답 찬양을 뺀다.
    음량은 부분마다 한 번 재서 고정 배율로 맞춘다 — loudnorm 동적 모드는 문장 사이 0.8초 쉼에서 음량을 끌어올렸다가
    다음 문장 첫소리에서 리미터가 급히 눌러 '칙' 소리를 냈다(10-24 사용자 지적). 부분 앞뒤는 20ms 페이드."""
    import music_library as ml
    files = []
    for p in script["parts"]:
        if "song" in p:
            s = p["song"]
            p["audio"] = str(song_audio(s))
            if s.get("source") == "local" and s.get("lyrics"):     # 직접 연주 찬송 — 가사.txt 로 자막 시각표
                s["lyrics_cues"] = ml.lyrics_cues(MUSIC_DIR / s["folder"], s["lyrics"], dur(Path(p["audio"])))
        elif "pm" in p:
            build_prayer_meeting(p, out)
        files.append((p, Path(p["audio"])))
    whole = lambda p: "song" in p or "pm" in p                       # 이미 완성된 소리(느리게 하지 않음)
    total = sum(dur(f) / (1 if whole(p) else SPEED) for p, f in files) + 1.5 * len(files)
    if total > MAX_MIN * 60:
        files = [(p, f) for p, f in files if p["id"] != "song2"]
        log(f"{MAX_MIN:g}분 초과({total / 60:.1f}분) → 응답 찬양 뺌")
    t, timeline = 0.0, []
    inputs, filters = [], []
    for i, (p, f) in enumerate(files):
        inputs += ["-i", str(f)]
        slow = not whole(p) and SPEED != 1
        body = dur(f) / (SPEED if slow else 1)
        gain = 0.0 if "pm" in p else max(-20.0, min(20.0, -16.0 - loudness(f)))   # 기도회는 안에서 이미 맞춤
        filters.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,"
                       + ("adeclick," if not whole(p) else "")       # 낭독에 남은 '칙' 고치기
                       + (f"atempo={SPEED}," if slow else "")
                       + f"volume={gain:.2f}dB,alimiter=limit=0.84:attack=5:release=80:level=disabled,"
                       + f"afade=t=in:d=0.02,afade=t=out:st={max(0.0, body - 0.02):.3f}:d=0.02,"
                       + f"apad=pad_dur=1.5[a{i}]")
        d = body + 1.5
        timeline.append({"id": p["id"], "title": p["title"], "start": round(t, 1), "sec": round(d, 1),
                         **({"song": {k: p["song"][k] for k in ("title", "album", "youtube", "cover", "type", "source",
                                                                 "credits") if k in p["song"]}} if "song" in p else {}),
                         **({"music": {k: p["music"][k] for k in ("title", "album", "youtube", "type", "source", "credits")
                                       if k in p["music"]}, "pm_marks": p["pm_marks"]} if "pm" in p else {})})
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
        for p in script["parts"]:                 # 맥미니 목소리 묶음(voice_bundle.py)은 파일 이름만 적혀 온다 → 이 폴더 기준
            if p.get("audio") and not Path(p["audio"]).is_absolute():
                p["audio"] = str(out / p["audio"])
            for v in (p.get("pm_audio") or {}).values():
                if not Path(v["audio"]).is_absolute():
                    v["audio"] = str(out / v["audio"])
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

"""
매일 온라인 예배 채널(@online-worship-24)에 예배에서 실제로 부른 자작 찬송·기도 연주곡을 곡별 영상으로 올린다.
영상 = Still Waters 앨범 업로드 때 만든 곡별 영상(suno-playlist output/<앨범>_project/tracks_mp4/track_NN.mp4).
설명 = 가사 + 곡 해설(앨범 원고 album.md 의 Track Notes 기준).

    python hymn_upload.py --dry-run            # 올릴 목록·제목·설명 길이만
    python hymn_upload.py --max 2              # 앞에서부터 최대 2곡 (이미 올린 곡은 건너뜀)
    python hymn_upload.py --show <key>         # 설명 전문 보기

중복 방지: 상태 파일 + 채널에 같은 제목 영상이 있으면 건너뜀.
할당량: 예배 송출과 같은 GCP 프로젝트(autovid, 16채널 공유) — 업로드 1곡 ≈ 1,650유닛.
할당량 초과(quotaExceeded/uploadLimitExceeded)면 거기서 멈추고 종료 코드 3.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = Path("/mnt/external/nexis-worship")
TOKEN = BASE / ".youtube_token_live.pickle"
STATE = BASE / "hymn_uploads_state.json"
SUNO = Path("/mnt/external/suno-playlist/output")
ALBUM_DIR = {"ko": "아침_찬송_1집_(Morning_Hymns,_Vol._1)_project", "en": "Hymns_for_the_Daily_Walk,_Vol._1_project"}
PLAYLIST = {"ko": ("예배 찬송 · 가사", "매일 온라인 예배에서 함께 부른 찬송과 기도 연주곡입니다. 가사와 곡 해설은 각 영상 설명에 있습니다."),
            "en": ("Worship Hymns with Lyrics", "Hymns and prayer pieces we sing and pray with in the Daily Online Worship. Lyrics and notes are in each description.")}

SCHED_KO = ["⛪ 매일 온라인 예배 — 날마다 새 예배를 드립니다(한국 시간)",
            "한국어  오전 10시 · 오후 4시 · 밤 10시 · 새벽 4시",
            "English  오후 1시 · 저녁 7시 · 새벽 1시 · 오전 7시"]
SCHED_EN = ["⛪ Daily Online Worship — a new service every day (Korea time)",
            "English  1 PM · 7 PM · 1 AM · 7 AM",
            "한국어  10 AM · 4 PM · 10 PM · 4 AM"]
MADE_KO = ["ℹ️ 만든 과정",
           "가사는 성경 본문을 바탕으로 새로 썼습니다(기존 찬송가·CCM 가사는 쓰지 않았습니다). 곡과 노래는 AI 음악 도구(Suno 유료 플랜)로 만든 자작곡입니다.",
           "🎵 Still Waters (yojosuknam) · 앨범 「아침 찬송 1집 (Morning Hymns, Vol. 1)」"]
MADE_EN = ["ℹ️ How this was made",
           "The words are newly written from Scripture (no existing hymn or CCM text is used). The music and voices were made with an AI music tool (Suno, paid plan) as original songs.",
           "🎵 Still Waters (yojosuknam) · album “Hymns for the Daily Walk, Vol. 1”"]
TAGS_KO = ["찬송가", "자작 찬송가", "새 찬송", "찬송 가사", "예배 찬송", "온라인 예배", "매일 예배", "아침 예배", "회중 찬송",
           "오르간 찬송", "피아노 찬송", "기도 음악", "묵상 음악", "Still Waters", "Korean hymn"]
TAGS_EN = ["hymn", "hymns", "new hymns", "original hymns", "hymn with lyrics", "congregational hymn", "traditional hymn",
           "organ hymn", "piano hymn", "prayer music", "online worship", "daily worship", "morning worship",
           "daily devotion", "Still Waters"]


def verses(text: str, ko: bool) -> list[str]:
    out = []
    for i, block in enumerate(text.strip().split("\n\n"), 1):
        out += [f"{i}절" if ko else f"Verse {i}", *block.strip().splitlines(), ""]
    return out


def vocal(lang, n, title, sub, ref, about, lyrics, confess, flow, music, place, sing, extra_tags):
    ko = lang == "ko"
    t = (f"{title} (가사) · {ref} | 자작 찬송가 · 매일 온라인 예배" if ko
         else f"{title} (Lyrics) · {ref} | New Hymn · Daily Online Worship")
    d = [f"{title} — {sub}", "", about, "",
         f"📖 {'본문' if ko else 'Scripture'} · {ref}", "",
         f"🎵 {'가사' if ko else 'Lyrics'}", *verses(lyrics, ko),
         f"✍️ {'곡 해설' if ko else 'About this hymn'}",
         f"• {'고백 한 문장' if ko else 'In one sentence'}: {confess}",
         *[f"• {x}" for x in flow],
         f"• {'음악' if ko else 'Music'}: {music}",
         f"• {'예배에서' if ko else 'In our worship'}: {place}", "",
         f"🙏 {'이렇게 불러 보세요' if ko else 'How to sing it'}", sing, "",
         *(SCHED_KO if ko else SCHED_EN), "",
         *(MADE_KO if ko else MADE_EN), "",
         ("#찬송가 #자작찬송가 #찬송가사 #온라인예배 #매일예배 " if ko else "#hymn #newhymn #hymnlyrics #onlineworship #dailyworship ")
         + " ".join("#" + x.replace(" ", "") for x in extra_tags)]
    return {"key": f"{lang}{n:02d}", "lang": lang, "n": n, "title": t, "desc": "\n".join(d),
            "tags": (TAGS_KO if ko else TAGS_EN) + extra_tags}


def instr(lang, n, title, sub, about, scene, music, place, pray, ref, extra_tags):
    ko = lang == "ko"
    t = (f"{title} · 기도 연주곡 (피아노·{'현악' if '현악' in music else '오르간'}) | 매일 온라인 예배" if ko
         else f"{title} · Prayer Piano Hymn | Daily Online Worship")
    d = [f"{title} — {sub}", "", about, "",
         f"🖼 {'장면' if ko else 'The scene'}", scene, "",
         f"✍️ {'곡 해설' if ko else 'About this piece'}",
         f"• {'음악' if ko else 'Music'}: {music}",
         f"• {'예배에서' if ko else 'In our worship'}: {place}",
         f"• {'함께 묵상할 말씀' if ko else 'Scripture to pray with'}: {ref}", "",
         f"🙏 {'이 곡과 함께 드리는 기도' if ko else 'Praying with this piece'}", *[f"{i}. {p}" for i, p in enumerate(pray, 1)], "",
         ("가사가 없는 곡입니다. 위 기도 제목을 하나씩 떠올리며 조용히 기도하거나, 말씀을 읽는 동안 배경으로 틀어 두세요." if ko
          else "There are no words in this piece. Take the prayers above one at a time, or let it play quietly while you read Scripture."), "",
         *(SCHED_KO if ko else SCHED_EN), "",
         *(MADE_KO if ko else MADE_EN), "",
         ("#기도음악 #기도연주곡 #찬송피아노 #묵상음악 #온라인예배 " if ko else "#prayermusic #hymnpiano #devotionalmusic #onlineworship #dailyworship ")
         + " ".join("#" + x.replace(" ", "") for x in extra_tags)]
    return {"key": f"{lang}{n:02d}", "lang": lang, "n": n, "title": t, "desc": "\n".join(d),
            "tags": (TAGS_KO if ko else TAGS_EN) + extra_tags}


SONGS = [
    # ── 예배에서 두 번 부른 응답 찬양부터 ──
    vocal("ko", 4, "마르지 않는 샘", "목마른 자의 간구 찬송", "이사야 55:1 · 예레미야 2:13 · 요한복음 4:14",
          "값없이 주시는 생수 앞에 빈 그릇을 들고 나아가는 간구의 찬송입니다. 스스로 웅덩이를 파며 지쳐 가던 마음이 주님의 샘에서 다시 채워지는 이야기를 네 절에 담았습니다.",
          """목마른 자 다 오라고
주가 나를 부르네
값도 없이 돈도 없이
맑은 샘이 솟아나

터진 웅덩이 파느라
내 손 지쳐 갈라져
헛된 물을 마셨으나
목마름만 더하네

이제 주께 나아가서
빈 그릇을 내미니
내 속에서 솟는 샘물
영원토록 흐르리

메마른 날 지날 때도
주의 샘이 넘치니
목마름이 노래 되어
주를 찬송하리라""",
          "터진 웅덩이를 파던 내가 빈 그릇을 들고 값없이 주시는 샘으로 나아갑니다.",
          ["1절 · 부르심 — \"목마른 자들아 물로 나아오라\"(사 55:1). 값도 돈도 없이 오라는 초대로 시작합니다.",
           "2절 · 고백 — 생수의 근원을 버리고 물을 담지 못할 터진 웅덩이를 판 백성(렘 2:13)처럼, 내 힘으로 애쓰다 더 목말랐던 날들을 고백합니다.",
           "3절 · 나아감 — 빈 그릇을 내미는 순간, 주님이 주시는 물이 속에서 영원히 솟는 샘이 됩니다(요 4:14).",
           "4절 · 확신 — 메마른 날에도 샘은 넘치고, 목마름 자체가 찬송이 됩니다."],
          "8.7.8.7 율격 · D단조(마지막 화음만 장조) · 68BPM · 피아노와 조용한 오르간, 작은 합창. 앨범에서 유일한 단조 찬송으로, 간구의 곡이라 1인칭 '나'로 썼습니다.",
          "기도회 바로 앞, 응답 찬양으로 불렀습니다.",
          "네 절 모두 같은 선율입니다. 1절은 들으며 가락을 익히고, 2절부터 가사를 보며 낮은 목소리로 따라 불러 보세요. 소리 내기 어려운 자리라면 마음속으로 가사를 음미하셔도 좋습니다.",
          ["이사야55장", "요한복음4장", "생수", "간구찬송"]),
    vocal("en", 4, "As Watchmen Wait for Morning", "a hymn of waiting prayer", "Psalm 130",
          "A prayer from the depths, set to a simple tune the whole congregation can sing. It brings the wrongs we cannot mend to the Lord and waits for His mercy the way a night watchman waits for the first light.",
          """From far below I lift my voice,
O Lord, attend my cry;
If You kept count of every wrong,
Then who could meet Your eye?

But there is mercy in Your hand,
And pardon comes from You;
I bring the wrongs I cannot mend
And trust what You will do.

My soul is waiting, Lord, for You
More than the watch for dawn;
I hope in every word You speak
Until the night is gone.

I will not fear the longest night,
The dawn is on its way;
With You is full redemption, Lord,
Your mercy holds the day.""",
          "From the depths I bring wrongs I cannot mend, and wait for Your mercy more than the night watch waits for dawn.",
          ["Verse 1 · The cry — \"Out of the depths have I cried unto thee\" (Ps 130:1-3). If the Lord kept a record of sins, no one could stand.",
           "Verse 2 · Confession — \"But there is forgiveness with thee\" (130:4). We bring what we cannot fix ourselves.",
           "Verse 3 · Waiting — \"My soul waiteth for the Lord more than they that watch for the morning\" (130:5-6).",
           "Verse 4 · Assurance — \"With him is plenteous redemption\" (130:7). The night is long, but the dawn is certain."],
          "Common Meter 8.6.8.6 (iambic) · E minor with a gentle major final chord · 66 BPM · soft piano and quiet organ with a small choir. The album's only minor-key hymn, written in the first person because it is a prayer.",
          "Sung as the response hymn just before the time of prayer.",
          "Every verse uses the same melody. Listen through verse 1, then sing along from verse 2 with the words on screen. If you cannot sing aloud, pray the words quietly in your heart.",
          ["Psalm130", "outofthedepths", "prayerhymn"]),
    # ── 여는 찬송 ──
    vocal("ko", 2, "반석 위에 세운 집", "말씀 위에 삶을 짓는 응답 찬송", "마태복음 7:24-27",
          "산상수훈을 마무리하는 예수님의 비유 — 말씀을 듣고 행하는 사람은 반석 위에 집을 지은 사람과 같다 — 를 따라 부르는 찬송입니다. 듣기만 하던 지난날을 고백하고, 오늘 들은 말씀을 손과 발로 쌓아 가겠다고 다짐합니다.",
          """주의 말씀 굳센 반석
흔들림이 없네
비바람이 몰아쳐도
그 자리 그대로

모래 위에 쌓은 집을
우리 자랑했네
듣기만 한 지난날들
용서하옵소서

오늘 들은 이 말씀을
삶으로 지으리
손과 발로 돌을 놓아
주 앞에 세우세

큰물 지고 바람 쳐도
우리 서 있으리
말씀 위에 지은 집은
넘어지지 않네""",
          "말씀을 듣기만 하던 우리가 이제 그 말씀 위에 삶을 짓겠습니다.",
          ["1절 · 하나님의 성품 — 비바람에도 흔들리지 않는 말씀의 반석.",
           "2절 · 고백 — 모래 위에 쌓은 집을 자랑하며 듣기만 했던 지난날을 용서해 달라고 구합니다(마 7:26).",
           "3절 · 순종 — 오늘 들은 말씀을 한 돌 한 돌 삶으로 쌓겠다는 다짐(마 7:24).",
           "4절 · 확신 — 큰물과 바람이 와도 말씀 위에 지은 집은 넘어지지 않습니다(마 7:25)."],
          "8.6.8.6 공통 운율(C.M.) · G장조 · 76BPM · 피아노가 이끌고 오르간이 받칩니다. 1절은 다 같이 한 목소리(제창), 2절부터 4성부 합창.",
          "예배를 여는 '함께 부르는 찬송'으로 불렀습니다.",
          "네 절 모두 같은 선율입니다. 1절은 들으며 가락을 익히고, 2절부터 화면 가사를 보며 함께 불러 보세요. 4절은 조금 더 힘 있게 — 확신의 절입니다.",
          ["마태복음7장", "산상수훈", "반석위의집"]),
    vocal("en", 2, "The Tree Beside the Stream", "a hymn of being rooted in the Word", "Psalm 1",
          "Psalm 1 sung as a congregational hymn: the one who delights in the law of the Lord is like a tree planted by rivers of water. We confess our drifting, and ask to be rooted deep enough to bear fruit for others.",
          """The Lord who knows the path we take
Has set a stream nearby,
Where roots go down and leaves stay green
Though summer fields are dry.

We sat where scorners sat at ease,
We walked the crowded road,
And blew like chaff before the wind
With nothing that could hold.

Now by Your word, both day and night,
We'll sink our roots down deep,
And bear our fruit in season due
For hungry hands to reap.

Our leaf shall never fade or fall,
The river does not cease;
The Lord who knows the path we take
Will lead us home in peace.""",
          "We stopped drifting like chaff and set our roots by His word, so our fruit can feed others.",
          ["Verse 1 · Who God is — \"The Lord knoweth the way of the righteous\" (Ps 1:6); He plants us by the water.",
           "Verse 2 · Confession — we sat in the seat of the scornful and blew away like chaff (1:1, 1:4).",
           "Verse 3 · Obedience — meditating on His law day and night, bearing fruit in season (1:2-3).",
           "Verse 4 · Assurance — the leaf does not wither; the opening line returns to close the hymn."],
          "Common Meter 8.6.8.6 (iambic) · G major · gentle 3/4 time, 74 BPM · piano leading with soft organ; verse 1 in unison, then a simple four-part choir. The album's only hymn in three.",
          "Sung as the opening hymn of the service.",
          "Same melody for every verse. Listen to verse 1, then join from verse 2. The last verse repeats the first line — sing it with confidence.",
          ["Psalm1", "treeplantedbythewater", "psalmhymn"]),
    vocal("ko", 5, "겸손히 함께 걷는 길", "공의·인자·겸손의 파송 찬송", "미가 6:8",
          "\"오직 공의를 행하며 인자를 사랑하며 겸손히 네 하나님과 함께 행하는 것\" — 미가 선지자가 전한 한 문장을 오늘 하루의 걸음으로 옮기는 파송 찬송입니다. 예배를 마치고 일상으로 나서는 자리에서 부릅니다.",
          """무엇이 선한 것인지
주가 보이셨네
제물보다 기뻐하실
참된 길 있으니

공의를 행하는 손과
인자 품은 마음
겸손히 주와 걷는 발
그것을 원하네

오늘 하루 이 길 위에
우리 나아가리
약한 이웃 손을 잡고
주와 동행하세

해가 지고 밤이 와도
주가 지키시니
새 아침에 다시 서서
그 길 걸으리라""",
          "주가 보이신 선한 길(공의·인자·겸손)을 오늘 하루 이웃과 함께 걷겠습니다.",
          ["1절 · 하나님의 뜻 — 제물보다 기뻐하시는 참된 길을 이미 보여 주셨습니다(미 6:6-8).",
           "2절 · 세 가지 — 공의를 행하는 손, 인자를 품은 마음, 겸손히 주와 걷는 발.",
           "3절 · 파송 — 오늘 하루, 약한 이웃의 손을 잡고 그 길로 나아갑니다.",
           "4절 · 확신 — 밤에도 지키시는 주님 안에서 새 아침에 다시 그 길을 걷습니다. 앨범 첫 곡(여는 찬송)과 수미상관을 이룹니다."],
          "8.6.8.6 공통 운율(C.M.) · B♭장조 · 78BPM, 걷는 속도 · 오르간과 피아노, 4성부 합창.",
          "예배를 여는 '함께 부르는 찬송'으로 불렀습니다.",
          "네 절 모두 같은 선율입니다. 걷는 속도로 또박또박 불러 보세요. 2절의 '손·마음·발'을 부를 때 오늘 내가 할 일 하나씩을 떠올려 보시면 좋습니다.",
          ["미가6장8절", "파송찬송", "공의와인자"]),
    vocal("en", 5, "Like a City on a Hill", "a hymn of sending", "Matthew 5:13-16",
          "Jesus calls His people the salt of the earth and the light of the world. This sending hymn confesses the lamp we hid and the salt we kept on the shelf, and asks to be sent out into the day so that people see the Father's goodness, not our names.",
          """Christ, the light of all creation,
Shines where weary people go;
He has called us salt and lantern,
So that all the world may know.

We have hid our lamp in corners,
Kept our salt upon the shelf;
Lord, forgive the light we covered
When we lived but for ourselves.

Send us out into the morning,
Out to market, field, and street;
Let our deeds be plain and kindly,
Bread for all the ones we meet.

Let them see the good You've given,
Not our names but Yours made bright;
Praise the Father, Son, and Spirit,
Source and end of every light.""",
          "We hid our lamp and kept our salt on the shelf; now send us out so the Father, not our name, is seen.",
          ["Verse 1 · Who Christ is — the light of all creation, who names us salt and light (Mt 5:13-14).",
           "Verse 2 · Confession — a lamp under a bushel, salt that lost its use (5:13, 5:15).",
           "Verse 3 · Sending — into market, field and street, with plain and kindly deeds.",
           "Verse 4 · Doxology — \"that they may see your good works, and glorify your Father\" (5:16); ends in praise to the Trinity."],
          "8.7.8.7 (trochaic) · F major · 82 BPM, a walking pace · organ and piano with a simple four-part choir.",
          "Sung as the opening hymn of the service.",
          "Same melody for every verse — sing it at a steady walking pace. In verse 3, think of one place you will go today.",
          ["Matthew5", "saltandlight", "cityonahill"]),
    # ── 기도회 배경 연주곡 ──
    instr("ko", 6, "안개 걷히는 능선", "Mist Lifting from the Ridge",
          "새벽 안개가 천천히 걷히고 능선 위로 첫 햇빛이 비치는 시간을 그린 기도 연주곡입니다. 여는 찬송 「깊은 땅도 높은 산도」(시편 95)의 분위기에서 출발해 새로 만든 곡입니다.",
          "골짜기에 깔린 안개, 첫 금빛을 받는 긴 산줄기. 아직 아무도 깨지 않은 아침에 창조주 앞에 홀로 서는 시간입니다.",
          "D장조 · 64BPM · 피아노가 선율을 차분히 짚고 오르간이 낮게 받칩니다. 크게 부풀지 않고 처음부터 끝까지 같은 숨으로 흐릅니다.",
          "기도회 배경 음악으로 썼습니다.",
          ["새 아침을 주신 것에 감사드립니다.", "오늘 내 마음에 깔린 안개(걱정·두려움)를 주님께 내어 드립니다.", "오늘 만날 사람들과 해야 할 일을 하나씩 떠올리며 맡깁니다."],
          "시편 95:1-7",
          ["시편95편", "아침기도", "새벽기도"]),
    instr("en", 6, "Last Stars Before Dawn", "a prayer piano piece",
          "A quiet prayer piece for the last hour of night, when the stars are fading and the horizon begins to fill with gold. It grew out of the opening hymn “He Calls the Stars by Name” (Isaiah 40).",
          "The same starry desert sky a little later: the stars softening, a few bright ones still above the hills, pale gold and blue rising at the edge of the world.",
          "E-flat major · 64 BPM · piano carrying a simple melody over soft sustained organ, unhurried from start to finish.",
          "Played as the background of the time of prayer.",
          ["Thank Him that He knows every star — and you — by name.", "Bring Him what kept you awake: the worries of the night.", "Ask for strength for the day ahead: \"they that wait upon the Lord shall renew their strength.\""],
          "Isaiah 40:26-31",
          ["Isaiah40", "morningprayer", "dawnprayer"]),
    instr("ko", 8, "새싹 돋는 밭", "Green Shoots in the Field",
          "씨를 뿌린 밭에 연둣빛 새싹이 줄지어 돋아난 아침을 그린 기도 연주곡입니다. 응답 찬송 「씨 뿌리는 아침」(마가복음 4장, 씨 뿌리는 비유)의 분위기에서 출발해 새로 만든 곡이며, 앨범에서 드문 3박자 곡입니다.",
          "갈아 놓은 밭이랑마다 작은 싹이 올라온 들판. 말씀이 마음 밭에 떨어져 조용히 자라나는 시간입니다.",
          "F장조 · 3/4박 · 60BPM · 피아노 선율 위에 현악 4중주가 부드럽게 화음을 받칩니다.",
          "기도회 배경 음악으로 썼습니다.",
          ["오늘 받은 말씀 한 구절을 마음에 다시 심습니다.", "내 마음의 굳은 길가·돌밭·가시덤불을 주님이 갈아 주시길 구합니다.", "말씀의 열매가 이웃에게 흘러가도록 한 사람을 떠올려 기도합니다."],
          "마가복음 4:3-20 · 시편 126:6 — \"울며 씨를 뿌리러 나가는 자는 정녕 기쁨으로 그 단을 가지고 돌아오리로다\"",
          ["마가복음4장", "씨뿌리는비유", "묵상기도"]),
    instr("en", 8, "Bread Left on the Table", "a prayer piano piece",
          "A tender prayer piece for the moment after Emmaus: the two disciples have recognized Jesus in the breaking of the bread, and He is gone — but the bread is still on the table and their hearts are burning. It grew out of the response hymn “Along the Emmaus Road” (Luke 24).",
          "A wayside inn late at night: bread and cups left behind, a chair pushed back, the door wide open onto a dark road under a few stars, the lamp still glowing.",
          "A major · 62 BPM · piano with a soft string quartet, warm and restrained.",
          "Played as the background of the time of prayer.",
          ["Remember a moment you knew the Lord was with you, even if you saw it only afterward.", "Ask Him to open the Scriptures to you as He did on the road.", "Pray for someone you can share bread with this week."],
          "Luke 24:28-35 — \"he was known of them in breaking of bread\"",
          ["Luke24", "roadtoemmaus", "communion"]),
]


def youtube():
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    c = pickle.loads(TOKEN.read_bytes())
    if not c.valid:
        c.refresh(Request())
        TOKEN.write_bytes(pickle.dumps(c))
    return build("youtube", "v3", credentials=c, cache_discovery=False)


def channel_titles(y) -> set[str]:
    up = y.channels().list(part="contentDetails", mine=True).execute()["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    titles, req = set(), y.playlistItems().list(part="snippet", playlistId=up, maxResults=50)
    while req:
        r = req.execute()
        titles |= {i["snippet"]["title"] for i in r.get("items", [])}
        req = y.playlistItems().list_next(req, r)
    return titles


def get_playlist(y, lang: str) -> str:
    title, desc = PLAYLIST[lang]
    req = y.playlists().list(part="id,snippet", mine=True, maxResults=50)
    while req:
        r = req.execute()
        for p in r.get("items", []):
            if p["snippet"]["title"] == title:
                return p["id"]
        req = y.playlists().list_next(req, r)
    return y.playlists().insert(part="snippet,status", body={
        "snippet": {"title": title, "description": desc, "defaultLanguage": lang},
        "status": {"privacyStatus": "public"}}).execute()["id"]


def quota_hit(e) -> bool:
    s = str(e)
    return "quotaExceeded" in s or "uploadLimitExceeded" in s or "dailyLimitExceeded" in s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0, help="이번에 올릴 최대 곡 수(0=전부)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show")
    a = ap.parse_args()
    for s in SONGS:
        assert len(s["title"]) <= 100, s["title"]
        assert len(s["desc"]) <= 5000 and "<" not in s["desc"] and ">" not in s["desc"], s["key"]
        assert sum(len(t) + 1 for t in s["tags"]) <= 480, s["key"]
    if a.show:
        s = next(x for x in SONGS if x["key"] == a.show)
        print(s["title"], "\n", s["desc"], "\n", s["tags"], sep="")
        return 0
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    todo = [s for s in SONGS if s["key"] not in state]
    if a.dry_run:
        for s in SONGS:
            v = SUNO / ALBUM_DIR[s["lang"]] / "tracks_mp4" / f"track_{s['n']:02d}.mp4"
            print(("done " if s["key"] in state else "todo ") + s["key"], "mp4" if v.exists() else "NO-MP4", len(s["desc"]), s["title"])
        return 0
    if not todo:
        print("모두 올림")
        return 0
    import worship_ops as ops
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    y = youtube()
    have = channel_titles(y)
    done = []
    for s in todo:
        if a.max and len(done) >= a.max:
            break
        if s["title"] in have:                       # 채널에 이미 같은 제목 → 중복 업로드 안 함
            state[s["key"]] = "exists"
            continue
        v = SUNO / ALBUM_DIR[s["lang"]] / "tracks_mp4" / f"track_{s['n']:02d}.mp4"
        body = {"snippet": {"title": s["title"], "description": s["desc"], "tags": s["tags"], "categoryId": "10",
                            "defaultLanguage": s["lang"], "defaultAudioLanguage": s["lang"]},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True, "embeddable": True}}
        try:
            req = y.videos().insert(part="snippet,status", body=body,
                                    media_body=MediaFileUpload(str(v), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True))
            r = None
            while r is None:
                _, r = req.next_chunk()
            vid = r["id"]
        except HttpError as e:
            if quota_hit(e):
                print(f"할당량 초과 — {s['key']} 에서 멈춤")
                STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
                ops.notify(f"⛪ 예배 찬송 업로드: 할당량 초과로 멈춤 ({len(done)}곡 올림, 남은 {len(todo) - len(done)}곡은 다음 회차)")
                return 3
            raise
        state[s["key"]] = vid
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            y.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": get_playlist(y, s["lang"]), "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        except HttpError as e:
            print(f"재생목록 추가 실패({s['key']}): {str(e)[:120]}")
        done.append((s, vid))
        print(f"올림 {s['key']} https://youtu.be/{vid} {s['title']}")
    left = len([s for s in SONGS if s["key"] not in state])
    if done:
        ops.notify("⛪ 예배 찬송 업로드\n" + "\n".join(f"• {s['title'].split(' · ')[0]} https://youtu.be/{v}" for s, v in done)
                   + f"\n남은 곡 {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

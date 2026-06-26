#!/usr/bin/env python3
"""Fetch YouTube playlists from configured channels and regenerate public/data.js"""

import json
import base64
import urllib.request
import urllib.parse
import os
import sys

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

CHANNELS = [
    {"handle": "Hanguk-Sounds",     "default_genre": "Hanguk Sounds"},
    {"handle": "MidnightRadio-h3t", "default_genre": "Midnight Radio"},
    {"handle": "Miso-Beats",        "default_genre": "Miso Beats"},
    # autovid/youtube-playlist 음악 채널 (2026-06-27 추가)
    {"handle": "nexis-song",        "default_genre": "굳이 송"},
    {"handle": "nexis-music",       "default_genre": "쉬어가는 감성 음악"},
    {"handle": "stillwaters-r7m",   "default_genre": "Still Waters"},
]

GENRE_KEYWORDS = {
    "CCM":          ["ccm", "worship", "praise", "hymn", "gospel", "찬양"],
    "K-Metal":      ["metal", "neon", "heavy", "rock"],
    "Lofi":         ["lofi", "lo-fi", "chill", "midnight", "radio", "sleep"],
    "Fusion":       ["fusion", "jazz", "blend"],
    "Instrumental": ["instrumental", "strings", "season", "piano", "acoustic"],
    "Beats":        ["beats", "hip-hop", "trap", "drill", "boom bap"],
    "K-Fusion":     ["korean", "hanguk", "한국", "traditional", "가야금"],
}


def guess_genre(title: str, default: str) -> str:
    lower = title.lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return genre
    return default


def yt_get(endpoint: str, params: dict) -> dict:
    params["key"] = YOUTUBE_API_KEY
    url = "https://www.googleapis.com/youtube/v3/" + endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_channel_info(handle: str) -> tuple[str, str] | tuple[None, None]:
    try:
        data = yt_get("channels", {"part": "id,contentDetails", "forHandle": handle})
    except Exception as e:
        print(f"ERROR fetching channel @{handle}: {e}", file=sys.stderr)
        return None, None
    items = data.get("items", [])
    if not items:
        print(f"WARNING: channel not found for handle @{handle}", file=sys.stderr)
        return None, None
    channel_id = items[0]["id"]
    uploads_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
    return channel_id, uploads_id


def get_videos(uploads_playlist_id: str, default_genre: str) -> list[dict]:
    result = []
    page_token = None
    while True:
        params: dict = {
            "part": "snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            data = yt_get("playlistItems", params)
        except Exception as e:
            print(f"ERROR fetching videos: {e}", file=sys.stderr)
            break
        for item in data.get("items", []):
            snippet = item["snippet"]
            video_id = snippet.get("resourceId", {}).get("videoId", "")
            if not video_id:
                continue
            thumbs = snippet.get("thumbnails", {})
            thumb = (
                thumbs.get("maxres")
                or thumbs.get("high")
                or thumbs.get("medium")
                or thumbs.get("default")
                or {}
            ).get("url", "")
            title = snippet.get("title", "")
            result.append({
                "genre": default_genre,
                "title": title,
                "playlist_url": f"https://www.youtube.com/watch?v={video_id}",
                "track_count": "1",
                "thumbnail_url": thumb,
                "source": "youtube-api",
                "status": "confirmed",
                "notes": "",
                "published_at": snippet.get("publishedAt", ""),
            })
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return result


def load_static_albums() -> list[dict]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "static_albums.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    print(f"Static albums: {len(data)}")
    return data


def main() -> None:
    if not YOUTUBE_API_KEY:
        print("ERROR: YOUTUBE_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    static_albums = load_static_albums()
    existing_urls = {a["playlist_url"] for a in static_albums}

    fetched: list[dict] = []
    for ch in CHANNELS:
        channel_id, uploads_id = get_channel_info(ch["handle"])
        if not uploads_id:
            continue
        videos = get_videos(uploads_id, ch["default_genre"])
        new_only = [v for v in videos if v["playlist_url"] not in existing_urls]
        print(f"@{ch['handle']}: {len(videos)} videos ({len(new_only)} new)")
        fetched.extend(new_only)

    all_albums = static_albums + fetched
    print(f"Total: {len(all_albums)} ({len(static_albums)} static + {len(fetched)} from YouTube)")

    json_str = json.dumps(all_albums, ensure_ascii=False)
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "..", "public", "data.js")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"window.SITE_DATA_B64='{b64}';\n")
    print(f"Written: {os.path.normpath(out_path)}")


if __name__ == "__main__":
    main()

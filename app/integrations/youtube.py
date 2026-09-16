"""
YouTube Integration
Full mode uses the YouTube Data API v3 (`youtube_api_key` credential) for search
and video metadata. Fallback mode plays/search via the default browser (works
with no credentials). Playback control (play/pause/next/previous) uses desktop
media-key simulation so it works on the actively-playing YouTube tab.

Capabilities: search_videos, search_channel, search_playlist, get_video_info,
open_video, play.
"""

import time
import webbrowser
import urllib.parse
from typing import Dict, Any, List, Optional

import requests

from app.integrations.credentials import get_setting, is_configured
from app.integrations.windows_control import hotkey, press_key

API = "https://www.googleapis.com/youtube/v3"


def _youtube_api_key() -> Optional[str]:
    return get_setting("youtube_api_key") or None


def _api_search(query_type: str, query: str, limit: int) -> Dict[str, Any]:
    key = _youtube_api_key()
    if not key:
        return {"success": False, "error": "No YouTube API key configured.", "hint": "Add youtube_api_key to the credentials block of config.json."}
    try:
        resp = requests.get(f"{API}/search", params={
            "part": "snippet", "q": query, "type": query_type,
            "maxResults": limit, "key": key,
        }, timeout=15)
        if resp.status_code != 200:
            return {"success": False, "error": f"YouTube API error {resp.status_code}: {resp.text[:200]}"}
        items = resp.json().get("items", [])
        results = [{
            "id": item["id"].get("videoId") or item["id"].get("channelId") or item["id"].get("playlistId"),
            "title": item["snippet"].get("title"),
            "channel": item["snippet"].get("channelTitle"),
            "description": item["snippet"].get("description", ""),
            "thumbnail": item["snippet"].get("thumbnails", {}).get("medium", {}).get("url"),
            "published_at": item["snippet"].get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={item['id'].get('videoId')}" if item["id"].get("videoId")
                   else f"https://www.youtube.com/channel/{item['id'].get('channelId')}" if item["id"].get("channelId")
                   else f"https://www.youtube.com/playlist?list={item['id'].get('playlistId')}",
        } for item in items]
        return {"success": True, "results": results, "count": len(results), "query": query}
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_videos(query: str, limit: int = 5, max_duration_minutes: Optional[int] = None) -> Dict[str, Any]:
    """Searches YouTube for videos. Optionally filters by max duration."""
    result = _api_search("video", query, limit)
    if not result.get("success"):
        return result
    if max_duration_minutes:
        videos = result["results"]
        info = []
        for v in videos:
            meta = get_video_info(v["id"])
            if meta.get("success") and meta.get("duration_minutes") is not None:
                if meta["duration_minutes"] <= max_duration_minutes:
                    info.append({**v, "duration_minutes": meta["duration_minutes"]})
            else:
                info.append(v)
        result["results"] = info
        result["count"] = len(info)
    result["output"] = f"Found {result['count']} video(s) for '{query}'."
    return result


def search_channel(query: str, limit: int = 5) -> Dict[str, Any]:
    result = _api_search("channel", query, limit)
    if result.get("success"):
        result["output"] = f"Found {result['count']} channel(s) for '{query}'."
    return result


def search_playlist(query: str, limit: int = 5) -> Dict[str, Any]:
    result = _api_search("playlist", query, limit)
    if result.get("success"):
        result["output"] = f"Found {result['count']} playlist(s) for '{query}'."
    return result


def get_video_info(video_id: str) -> Dict[str, Any]:
    """Returns duration, title, channel and view counts for a video."""
    key = _youtube_api_key()
    if not key:
        return {"success": False, "error": "Video metadata requires a YouTube API key."}
    try:
        resp = requests.get(f"{API}/videos", params={
            "part": "snippet,contentDetails,statistics", "id": video_id, "key": key,
        }, timeout=15)
        if resp.status_code != 200 or not resp.json().get("items"):
            return {"success": False, "error": "Video not found or API error."}
        item = resp.json()["items"][0]
        duration = item.get("contentDetails", {}).get("duration", "PT0S")
        seconds = _iso8601_to_seconds(duration)
        d = item["snippet"]
        return {
            "success": True,
            "id": video_id,
            "title": d.get("title"),
            "channel": d.get("channelTitle"),
            "duration_minutes": round(seconds / 60, 1) if seconds else None,
            "duration_iso": duration,
            "views": item.get("statistics", {}).get("viewCount"),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "output": f"{d.get('title')} by {d.get('channelTitle')}."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _iso8601_to_seconds(iso: str) -> int:
    import re
    match = re.search(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", iso)
    if not match:
        return 0
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s


def search_open_browser(query: str) -> Dict[str, Any]:
    """Opens a YouTube search results page in the default browser."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"
    try:
        webbrowser.open(url)
        return {"success": True, "url": url, "method": "browser", "output": f"Opened YouTube search for '{query}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def open_video(video_id: str = None, video_url: str = None, query: str = None) -> Dict[str, Any]:
    """
    Opens a video by id/url, or the first search result for a query
    (API mode resolves the exact video; fallback opens the search page).
    """
    if video_url:
        try:
            webbrowser.open(video_url)
            return {"success": True, "url": video_url, "output": f"Opened video {video_url}."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    if video_id:
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            webbrowser.open(url)
            return {"success": True, "url": url, "output": f"Opened video {video_id}."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    if query:
        if _youtube_api_key():
            res = search_videos(query, limit=1)
            if res.get("success") and res["results"]:
                return open_video(video_id=res["results"][0]["id"])
        return search_open_browser(query)
    return {"success": False, "error": "Provide video_id, video_url or query."}


def play(query: str = None, video_url: str = None) -> Dict[str, Any]:
    """Plays a video/query: opens it and issues a media-play key."""
    res = open_video(query=query) if not video_url else open_video(video_url=video_url)
    if not res.get("success"):
        return res
    time.sleep(3)
    press_key("playpause")
    return {**res, "output": f"Playing on YouTube: {query or video_url}."}


def pause() -> Dict[str, Any]:
    """Pauses the active YouTube tab using the media key."""
    time.sleep(0.2)
    press_key("playpause")
    return {"success": True, "output": "Toggled play/pause on YouTube."}


def next_video() -> Dict[str, Any]:
    hotkey("shift", "n")
    return {"success": True, "output": "Skipped to the next YouTube video."}


def previous_video() -> Dict[str, Any]:
    hotkey("shift", "p")
    return {"success": True, "output": "Went back to the previous YouTube video."}
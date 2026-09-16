"""
Spotify Deep Integration
Two execution tiers:

1. FULL API MODE  - uses the official Spotify Web API (OAuth PKCE). Requires
   `spotify_client_id`, `spotify_client_secret`, `spotify_redirect_uri` in the
   `credentials` block of config.json. Only this mode supports volume control,
   current track and playback state queries.
2. GUI/URI FALLBACK - no credentials needed. Drives the desktop app through
   `spotify:` URI scheme commands (open / search / play / pause / next / previous).

The agent decides which tier to use based on which credentials are configured.
"""

import os
import json
import webbrowser
import base64
import hashlib
import urllib.parse
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any, List, Optional

import requests

from app.integrations.credentials import get_setting, is_configured, missing_for
from app.core.config import load_config, save_config

API_BASE = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
CALLBACK_PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"

# Scopes required for the Playback + Playlist features the agent exposes.
SCOPES = " ".join([
    "user-modify-playback-state",
    "user-read-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-modify",
])


def _set_tokens(token_data: Dict[str, Any]) -> None:
    cfg = load_config()
    creds = cfg.setdefault("credentials", {})
    creds["spotify_access_token"] = token_data.get("access_token")
    creds["spotify_refresh_token"] = token_data.get("refresh_token", creds.get("spotify_refresh_token"))
    import time
    creds["spotify_token_expiry"] = int(time.time()) + int(token_data.get("expires_in", 3600))
    save_config(cfg)


def _get_token() -> Optional[str]:
    """Returns a valid access token, refreshing it if needed."""
    creds = load_config().get("credentials", {})
    access = creds.get("spotify_access_token")
    refresh = creds.get("spotify_refresh_token")
    expiry = creds.get("spotify_token_expiry", 0)
    import time
    if access and int(expiry) > int(time.time()) + 60:
        return access
    if refresh:
        return _refresh_access_token(refresh)
    return access


def _refresh_access_token(refresh_token: str) -> Optional[str]:
    client_id = get_setting("spotify_client_id")
    client_secret = get_setting("spotify_client_secret")
    try:
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }, timeout=15)
        if resp.status_code == 200:
            _set_tokens(resp.json())
            return resp.json().get("access_token")
    except Exception:
        pass
    return None


def _api_headers() -> Dict[str, str]:
    token = _get_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _api(method: str, path: str, **kwargs) -> Dict[str, Any]:
    """Thin wrapper around the Spotify Web API returning a normalized result dict."""
    ok, hint = missing_for("spotify_client_id")
    if not ok:
        return {"success": False, "error": "Spotify Web API is not configured.", "hint": hint}
    try:
        resp = requests.request(method, API_BASE + path, headers=_api_headers(), timeout=15, **kwargs)
        if resp.status_code in (200, 201, 204):
            data = resp.json() if resp.content else {}
            return {"success": True, "status_code": resp.status_code, "data": data}
        if resp.status_code in (401, 403) and get_setting("spotify_refresh_token"):
            _refresh_access_token(get_setting("spotify_refresh_token"))
            resp = requests.request(method, API_BASE + path, headers=_api_headers(), timeout=15, **kwargs)
            if resp.status_code in (200, 201, 204):
                return {"success": True, "data": resp.json() if resp.content else {}}
        if resp.status_code == 404:
            return {"success": False, "error": "No active Spotify device found. Open Spotify on any device first."}
        return {"success": False, "status_code": resp.status_code, "error": resp.text[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================================
# OAuth (PKCE) AUTHORIZATION FLOW
# ==========================================================
def _pkce_pair() -> tuple:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            type(self).code = query["code"][0]
            body = b"<html><body><h2>Spotify authorized. You can close this window.</h2></body></html>"
        else:
            body = b"<html><body><h2>Authorization cancelled or failed.</h2></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _exchange_code(verifier: str, code: str) -> Dict[str, Any]:
    client_id = get_setting("spotify_client_id")
    client_secret = get_setting("spotify_client_secret")
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": verifier,
    }, timeout=15)
    return resp.json() if resp.status_code == 200 else {}


def authenticate_spotify() -> Dict[str, Any]:
    """Runs the PKCE authorization-code flow with a local callback server."""
    ok, hint = missing_for("spotify_client_id")
    if not ok:
        return {"success": False, "error": "Spotify client credentials are required.", "hint": hint}

    client_id = get_setting("spotify_client_id")
    verifier, challenge = _pkce_pair()
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "show_dialog": "true",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    webbrowser.open(auth_url)

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    server.handle_request()  # blocks until one request arrives

    code = _CallbackHandler.code
    if not code:
        return {"success": False, "error": "Spotify authorization was not completed."}
    tokens = _exchange_code(verifier, code)
    if not tokens.get("access_token"):
        return {"success": False, "error": "Failed to exchange authorization code for tokens."}
    _set_tokens(tokens)
    return {"success": True, "output": "Spotify successfully authenticated with the Web API."}


# ==========================================================
# DESKTOP URI FALLBACK (no API credentials required)
# ==========================================================
def _open_spotify_uri(uri: str) -> Dict[str, Any]:
    try:
        subprocess.Popen(f'cmd /c start "" "{uri}"', shell=True)
        return {"success": True, "uri": uri}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================================
# CAPABILITY FUNCTIONS  (the agent calls these directly)
# ==========================================================
def open_spotify() -> Dict[str, Any]:
    """Opens the Spotify desktop application."""
    res = _open_spotify_uri("spotify:")
    return {**res, "output": "Opening Spotify."} if res.get("success") else {**res, "error": res.get("error", "Failed to open Spotify.")}


def search_spotify(query: str, limit: int = 5) -> Dict[str, Any]:
    """Searches tracks, artists, albums and playlists on Spotify."""
    if not query:
        return {"success": False, "error": "No search query provided."}
    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri(f"spotify:search:{urllib.parse.quote(query)}")
        return {**res, "output": f"Opened Spotify search for '{query}' in the desktop app."} if res.get("success") else res
    result = _api("GET", f"/search?q={urllib.parse.quote(query)}&type=track,artist,album,playlist&limit={limit}")
    if not result.get("success"):
        return result
    data = result["data"]
    def fmt(items, key):
        return [{"name": i.get("name"), "uri": i.get("uri"), "artists": ", ".join(a.get("name") for a in i.get("artists", [])[:3])} for i in items.get("items", [])]
    return {
        "success": True,
        "query": query,
        "tracks": fmt(data.get("tracks", {}), "tracks"),
        "artists": [{"name": a.get("name"), "uri": a.get("uri")} for a in data.get("artists", {}).get("items", [])],
        "albums": [{"name": a.get("name"), "uri": a.get("uri"), "artists": ", ".join(x.get("name") for x in a.get("artists", []))} for a in data.get("albums", {}).get("items", [])],
        "playlists": [{"name": p.get("name"), "uri": p.get("uri")} for p in data.get("playlists", {}).get("items", [])],
        "output": f"Found results for '{query}'.",
    }


def play_spotify(query: str = None, uri: str = None) -> Dict[str, Any]:
    """
    Plays a track / artist / album / playlist.
    - Pass a `spotify:` URI directly, or
    - Pass a human query like "Believer by Imagine Dragons" (resolved to the top track).
    """
    if uri:
        result = _api("PUT", "/me/player/play", json={"uris": [uri]})
        if not result.get("success"):
            result = _api("PUT", "/me/player/play", json={"context_uri": uri})
        return {**result, "output": f"Playing {uri}."} if result.get("success") else result

    if not query:
        return {"success": False, "error": "Nothing to play. Provide a song, artist or playlist."}

    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri(f"spotify:search:{urllib.parse.quote(query)}")
        return {**res, "output": f"Searching Spotify desktop for '{query}'."} if res.get("success") else res

    search = search_spotify(query, limit=1)
    if not search.get("success") or not search.get("tracks"):
        return {"success": False, "error": f"No track found matching '{query}'."}
    track = search["tracks"][0]
    result = _api("PUT", "/me/player/play", json={"uris": [track["uri"]]})
    return {
        **result,
        "track": track["name"],
        "artist": track["artists"],
        "output": f"Playing '{track['name']}' by {track['artists']}."
    } if result.get("success") else result


def play_playlist(playlist_name: str = None, playlist_uri: str = None) -> Dict[str, Any]:
    """Plays a saved playlist by name or by URI."""
    if playlist_uri:
        return play_spotify(uri=playlist_uri)
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Playlist playback by name requires Spotify Web API credentials."}
    playlists = get_playlists()
    if not playlists.get("success"):
        return playlists
    target = (playlist_name or "").strip().lower()
    for pl in playlists.get("playlists", []):
        if target in pl["name"].lower():
            return play_spotify(uri=pl["uri"])
    return {"success": False, "error": f"No playlist found matching '{playlist_name}'.", "playlists": playlists.get("playlists", [])}


def pause_spotify() -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri("spotify:pause")
        return {**res, "output": "Pausing Spotify."} if res.get("success") else res
    result = _api("PUT", "/me/player/pause")
    return {**result, "output": "Spotify paused."} if result.get("success") else result


def resume_spotify() -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri("spotify:play")
        return {**res, "output": "Resuming Spotify."} if res.get("success") else res
    result = _api("PUT", "/me/player/play")
    return {**result, "output": "Spotify resumed."} if result.get("success") else result


def next_track() -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri("spotify:next")
        return {**res, "output": "Skipping to the next track."} if res.get("success") else res
    result = _api("POST", "/me/player/next")
    return {**result, "output": "Skipped to the next track."} if result.get("success") else result


def previous_track() -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        res = _open_spotify_uri("spotify:previous")
        return {**res, "output": "Going back to the previous track."} if res.get("success") else res
    result = _api("POST", "/me/player/previous")
    return {**result, "output": "Went back to the previous track."} if result.get("success") else result


def set_volume(level: int, device_id: str = None) -> Dict[str, Any]:
    """Sets Spotify playback volume (0-100). Requires API mode."""
    level = max(0, min(100, int(level)))
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Spotify volume requires the Web API. Configure spotify_client_id in config.json."}
    url = f"/me/player/volume?volume_percent={level}"
    if device_id:
        url += f"&device_id={device_id}"
    result = _api("PUT", url)
    return {**result, "output": f"Spotify volume set to {level}%."} if result.get("success") else result


def shuffle(on: bool = True) -> Dict[str, Any]:
    state = "true" if on else "false"
    result = _api("PUT", f"/me/player/shuffle?state={state}")
    return {**result, "output": "Shuffle enabled." if on else "Shuffle disabled."} if result.get("success") else result


def get_current_track() -> Dict[str, Any]:
    """Returns what is currently playing (track, artist, album, progress)."""
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Current track queries require the Spotify Web API."}
    result = _api("GET", "/me/player/currently-playing")
    if not result.get("success") or not result.get("data"):
        return {"success": False, "error": "Nothing is currently playing or no active device."}
    item = result["data"].get("item", {})
    return {
        "success": True,
        "name": item.get("name"),
        "artists": ", ".join(a.get("name") for a in item.get("artists", [])),
        "album": item.get("album", {}).get("name"),
        "duration_ms": item.get("duration_ms"),
        "progress_ms": result["data"].get("progress_ms"),
        "is_playing": result["data"].get("is_playing"),
        "uri": item.get("uri"),
        "output": f"'{item.get('name')}' by {', '.join(a.get('name') for a in item.get('artists', []))} is playing."
    }


def get_playback_state() -> Dict[str, Any]:
    """Returns detailed playback state (device, volume, shuffle, repeat)."""
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Playback state requires the Spotify Web API."}
    result = _api("GET", "/me/player")
    if not result.get("success") or not result.get("data"):
        return {"success": False, "error": "No active playback session found."}
    d = result["data"]
    item = d.get("item", {}) or {}
    return {
        "success": True,
        "is_playing": d.get("is_playing"),
        "device": d.get("device", {}),
        "volume_percent": d.get("device", {}).get("volume_percent"),
        "shuffle": d.get("shuffle_state"),
        "repeat": d.get("repeat_state"),
        "track": item.get("name"),
        "artists": ", ".join(a.get("name") for a in item.get("artists", [])),
        "output": "Playback is active." if d.get("is_playing") else "Playback is paused."
    }


def get_devices() -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Device listing requires the Spotify Web API."}
    result = _api("GET", "/me/player/devices")
    if not result.get("success"):
        return result
    devices = [{"id": d.get("id"), "name": d.get("name"), "type": d.get("type"), "is_active": d.get("is_active")}
               for d in result["data"].get("devices", [])]
    return {"success": True, "devices": devices, "output": f"Found {len(devices)} device(s)."}


def get_playlists(limit: int = 20) -> Dict[str, Any]:
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "Playlist listing requires the Spotify Web API."}
    result = _api("GET", f"/me/playlists?limit={limit}")
    if not result.get("success"):
        return result
    playlists = [{"name": p.get("name"), "uri": p.get("uri"), "tracks_total": p.get("tracks", {}).get("total", 0)}
                 for p in result["data"].get("items", [])]
    return {"success": True, "playlists": playlists, "output": f"Found {len(playlists)} playlist(s)."}


def add_track_to_playlist(track_uri: str = None, query: str = None, playlist_name: str = None, playlist_uri: str = None) -> Dict[str, Any]:
    """Adds a track (by URI or search query) to a playlist (by URI or name)."""
    if not is_configured("spotify_client_id"):
        return {"success": False, "error": "This action requires the Spotify Web API."}
    if not track_uri and not query:
        return {"success": False, "error": "Provide the track URI or a track name to add."}
    if track_uri is None:
        search = search_spotify(query, limit=1)
        if not search.get("success") or not search.get("tracks"):
            return {"success": False, "error": f"No track found for '{query}'."}
        track_uri = search["tracks"][0]["uri"]

    if not playlist_uri:
        found = None
        for pl in (get_playlists(limit=50).get("playlists") or []):
            if playlist_name and playlist_name.lower() in pl["name"].lower():
                found = pl["uri"]
                break
        if not found:
            return {"success": False, "error": f"Playlist '{playlist_name}' not found."}
        playlist_uri = found

    playlist_id = playlist_uri.split(":")[-1]
    result = _api("POST", f"/playlists/{playlist_id}/tracks", json={"uris": [track_uri]})
    return {**result, "output": f"Added track to playlist."} if result.get("success") else result
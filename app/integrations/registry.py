"""
Application Capability System
A central registry describing every app the agent can drive, together with the
granular capabilities each app exposes. The LLM inspects `capability_summary_text()`
before selecting a tool; the dispatcher (`app.integrations.dispatcher`) performs the
actual (app, capability) -> function resolution.

Structure:
    APPLICATIONS[app_key] = {
        "name": <display name>,
        "capabilities": [caps...],
        "tool_layer": <module path>   # informational
    }
"""

from typing import Dict, Any, List, Optional

APPLICATIONS: Dict[str, Dict[str, Any]] = {
    "spotify": {
        "name": "Spotify",
        "description": "Music streaming (Web API when authenticated, desktop URI fallback).",
        "capabilities": [
            "open", "search", "play", "pause", "resume", "next", "previous",
            "shuffle", "volume", "current_track", "playback_state", "playlists",
            "add_track_to_playlist", "get_devices",
        ],
        "tool_layer": "app.integrations.spotify",
    },
    "browser": {
        "name": "Browser",
        "description": "Playwright-driven web automation (Chrome / Edge / Firefox).",
        "capabilities": [
            "open", "open_url", "search_web", "find_text", "click", "type",
            "scroll", "read_webpage_text", "download_file", "upload_file",
            "screenshot", "page_state",
        ],
        "tool_layer": "app.integrations.browser",
    },
    "filesystem": {
        "name": "File System",
        "description": "Search / read / create / edit / delete / convert files and folders.",
        "capabilities": [
            "search_files", "read_file", "read_pdf", "read_docx", "read_xlsx",
            "read_csv", "read_json", "read_pptx", "read_zip", "create_file",
            "create_csv", "edit_file", "delete_file", "move_file", "rename_file",
            "open_file", "create_folder", "list_directory", "convert_file",
            "search_inside_files", "get_file_info",
        ],
        "tool_layer": "app.integrations.file_system",
    },
    "windows": {
        "name": "Windows Control",
        "description": "Native Windows window, input, clipboard, volume and network control.",
        "capabilities": [
            "foreground_window", "minimize_window", "maximize_window",
            "switch_windows", "screenshot", "keyboard_input", "mouse_move",
            "mouse_click", "mouse_scroll", "clipboard_set", "clipboard_get",
            "set_volume", "get_volume", "get_brightness", "set_brightness",
            "wifi_status", "bluetooth_status", "battery_info", "monitor_cpu_ram",
        ],
        "tool_layer": "app.integrations.windows_control",
    },
    "app_launcher": {
        "name": "Application Launcher",
        "description": "Dynamic discovery and launch / close of installed applications.",
        "capabilities": [
            "discover_apps", "open_application", "close_application",
            "is_app_installed", "suggest_paths",
        ],
        "tool_layer": "app.integrations.app_launcher",
    },
    "youtube": {
        "name": "YouTube",
        "description": "YouTube search and playback (Data API v3 when key provided).",
        "capabilities": [
            "search_videos", "search_channel", "search_playlist", "get_video_info",
            "open_video", "play",
        ],
        "tool_layer": "app.integrations.youtube",
    },
    "github": {
        "name": "GitHub",
        "description": "GitHub via official REST API (personal access token).",
        "capabilities": [
            "get_user", "list_repos", "create_repo", "create_issue", "list_issues",
            "create_branch", "list_commits", "create_pr", "list_pull_requests",
            "search_repos",
        ],
        "tool_layer": "app.integrations.github",
    },
    "google": {
        "name": "Google Services",
        "description": "Google Drive, Gmail and Calendar via official Google APIs.",
        "capabilities": [
            "search_drive", "create_calendar_event", "today_meetings",
            "search_gmail", "draft_email", "send_email",
        ],
        "tool_layer": "app.integrations.google",
    },
    "discord": {
        "name": "Discord",
        "description": "Discord messaging via bot token REST API.",
        "capabilities": [
            "list_channels", "read_messages", "send_message", "search_messages",
            "get_channel_info",
        ],
        "tool_layer": "app.integrations.discord",
    },
}

# Human-friendly wording used by the intent matcher / LLM prompt.
CAPABILITY_ALIASES: Dict[str, List[str]] = {
    "spotify": ["music", "song", "playlist", "artist", "track"],
    "browser": ["chrome", "edge", "firefox", "web", "internet", "page", "website", "online"],
    "filesystem": ["file", "files", "folder", "pdf", "document", "text file", "csv", "excel"],
    "windows": ["volume", "brightness", "clipboard", "wifi", "bluetooth", "window", "mouse", "keyboard"],
    "app_launcher": ["open app", "launch", "application", "program"],
    "youtube": ["video", "youtube", "yt"],
    "github": ["repo", "repository", "commit", "pull request", "issue", "branch", "github"],
    "google": ["gmail", "drive", "calendar", "meeting", "email", "google"],
    "discord": ["discord", "message"],
}


def get_application(app_key: str) -> Optional[Dict[str, Any]]:
    """Returns the registry entry for an app key (case-insensitive)."""
    if not app_key:
        return None
    return APPLICATIONS.get(app_key.strip().lower())


def list_applications() -> List[Dict[str, str]]:
    """Returns a lightweight list of registered applications."""
    return [
        {"key": key, "name": entry["name"], "capabilities": entry["capabilities"]}
        for key, entry in APPLICATIONS.items()
    ]


def get_capabilities(app_key: str) -> List[str]:
    """Returns the capability list for an application (empty if unknown)."""
    entry = get_application(app_key)
    return list(entry["capabilities"]) if entry else []


def has_capability(app_key: str, capability: str) -> bool:
    """Checks whether an application exposes the given capability."""
    entry = get_application(app_key)
    return bool(entry and capability in entry["capabilities"])


def resolve_app_key(phrase: str) -> Optional[str]:
    """Maps a free-text mention (e.g. 'youtube') to a registry app key."""
    if not phrase:
        return None
    p = phrase.strip().lower()
    if p in APPLICATIONS:
        return p
    for key, aliases in CAPABILITY_ALIASES.items():
        for alias in aliases:
            if alias in p:
                return key
    return None


def find_capability(phrase: str) -> Optional[str]:
    """
    Attempts to match a user phrase to a (app_key, capability) pair.
    Returns '<app_key>.<capability>' or None.
    """
    p = phrase.strip().lower()
    for app_key, entry in APPLICATIONS.items():
        for cap in entry["capabilities"]:
            token = cap.replace("_", " ")
            if token == p or (token in p and len(p) <= len(cap) + 12):
                return f"{app_key}.{cap}"
    return None


def capability_summary_text() -> str:
    """Text summary injected into the LLM prompt so it can select the right tool."""
    lines = []
    for key, entry in APPLICATIONS.items():
        caps = ", ".join(entry["capabilities"])
        lines.append(f"- {key} ({entry['name']}): {caps}")
    return "\n".join(lines)


def credential_status_text() -> str:
    """Reports which integrations run in full API mode vs GUI/fallback mode."""
    from app.integrations.credentials import describe_status  # local import avoids cycle

    status = describe_status()
    tokens = {
        "spotify": "full API" if status.get("spotify_api") else "desktop URI fallback",
        "github": "API" if status.get("github_api") else "not configured",
        "google": "API" if status.get("google_api") else "not configured",
        "discord": "API" if status.get("discord_api") else "not configured",
        "youtube": "API" if status.get("youtube_api") else "browser fallback",
    }
    return " | ".join(f"{k}: {v}" for k, v in tokens.items())
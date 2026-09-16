"""
LLM Function Calling & Action Execution Engine (Ollama)
Forces Ollama to output structured JSON action payloads and coordinates execution across native system modules.
"""

import os
import re
import json
import requests
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from app.core.config import load_config
from app.core.app_launcher import launch_application, close_application
from app.core.task_automation import (
    lock_workstation, 
    get_detailed_telemetry, 
    execute_web_search, 
    execute_open_url, 
    execute_shell_task
)
from app.core.youtube_automation import play_youtube
from app.core.code_writer import generate_and_open_code
from app.core.file_manager import create_text_file, read_text_file, list_storage_files
from app.core.system_control import (
    set_volume, increase_volume, decrease_volume,
    mute_volume, shutdown_pc, restart_pc, cancel_shutdown
)
from app.integrations.dispatcher import execute_tool, get_tool
from app.integrations.registry import capability_summary_text, credential_status_text, list_applications
from app.integrations import app_launcher as integration_launcher

SYSTEM_FUNCTION_CALLING_PROMPT = """You are an autonomous AI Voice Assistant operating on the workstation of Prajwal Pradhan.
You are a  Full-Stack Developer (creator of ShopHub and advanced AI portfolios).
You MUST address him with respect as  'Sir'.
You have direct capability to execute actions on the operating system.

When Founder Prajjwal gives a command, you MUST respond in valid JSON matching one of the following action schemas:

1. Launch an application:
   {"action": "open_app", "target": "<app_name>", "response": "<spoken confirmation addressing  Sir>"}
   Examples:
   - "Open VS Code" -> {"action": "open_app", "target": "vs code", "response": "Opening Visual Studio Code is open for you ."}
   - "Open Chrome" -> {"action": "open_app", "target": "chrome", "response": "Launching Google Chrome right away, Sir."}

2. Close an application / process:
   {"action": "close_app", "target": "<app_name>", "response": "<spoken confirmation addressing  Sir>"}
   Example:
   - "Close Notepad" -> {"action": "close_app", "target": "notepad", "response": "Closing Notepad, Sir."}

3. Lock the screen / workstation:
   {"action": "lock_screen", "response": "Locking your workstation now, sir."}

4. Check system telemetry & hardware diagnostics (CPU, RAM, GPU, Battery):
   {"action": "system_telemetry", "response": "Fetching real-time system performance for you, Sir."}

5. Search the web:
   {"action": "web_search", "query": "<search_query>", "response": "<short confirmation addressing  Sir>"}

6. Open a specific website URL:
   {"action": "open_url", "url": "<url>", "response": "<short confirmation addressing  Sir>"}

7. Run custom shell command:
   {"action": "shell_command", "command": "<cmd>", "response": "<short confirmation addressing Sir>"}

8. Play YouTube video / music / search YouTube:
   {"action": "play_youtube", "query": "<song or video name>", "response": "<spoken confirmation>"}
   Examples:
   - "Play Believer on YouTube" -> {"action": "play_youtube", "query": "Believer Imagine Dragons", "response": "Playing Believer by Imagine Dragons on YouTube, Sir."}
   - "Search YouTube for Python tutorial" -> {"action": "play_youtube", "query": "Python tutorial for beginners", "response": "Searching YouTube for Python tutorials, Sir."}

9. Generate code and open in VS Code:
   {"action": "write_code", "description": "<what to code>", "language": "<python|javascript|etc>", "filename": "<optional filename>", "response": "<spoken confirmation>"}
   Example:
   - "Write a Python script for a calculator" -> {"action": "write_code", "description": "a Python calculator with basic arithmetic operations", "language": "python", "response": "Generating the calculator script and opening it in VS Code for you, Sir."}

10. Read a file from storage:
    {"action": "read_file", "filepath": "<path or filename>", "response": "<spoken confirmation>"}

11. Write / create a new text file:
    {"action": "write_file", "filename": "<filename.txt>", "content": "<content to write>", "response": "<spoken confirmation>"}

12. Volume Control:
    {"action": "volume_up", "step": 10, "response": "Increasing volume, Sir."}
    {"action": "volume_down", "step": 10, "response": "Decreasing volume, Sir."}
    {"action": "set_volume", "level": 70, "response": "Setting volume to 70 percent, Sir."}
    {"action": "mute_volume", "response": "Muting audio, Sir."}

13. Shutdown the PC:
    {"action": "shutdown_pc", "delay": 5, "response": "Initiating system shutdown in 5 seconds, sir."}

14. Restart the PC:
    {"action": "restart_pc", "delay": 5, "response": "Restarting the system in 5 seconds, Sir."}

15. General Conversation / Questions / No action required:
    {"action": "chat", "response": "<your conversational answer addressing  Sir>"}

16. EXECUTE ANY REGISTERED CAPABILITY TOOL:
    The agent maintains an APPLICATION CAPABILITY REGISTRY. Inspect the
    AVAILABLE CAPABILITIES list below, select the correct application and the
    precise capability it exposes, then emit:
    {"action": "tool", "app": "<app_key>", "capability": "<capability>", "params": {<param>: <value>}, "response": "<spoken confirmation>"}
    Examples:
    - "Play Believer by Imagine Dragons" -> {"action": "tool", "app": "spotify", "capability": "play", "params": {"query": "Believer Imagine Dragons"}, "response": "Playing Believer by Imagine Dragons, Sir."}
    - "Play my workout playlist" -> {"action": "tool", "app": "spotify", "capability": "play_playlist", "params": {"playlist_name": "workout"}, "response": "Playing your workout playlist, Sir."}
    - "What song is playing?" -> {"action": "tool", "app": "spotify", "capability": "current_track", "params": {}, "response": "Let me check what is playing."}
    - "Search YouTube for Python DSA tutorial" -> {"action": "tool", "app": "youtube", "capability": "search_videos", "params": {"query": "Python DSA tutorial"}, "response": "Searching YouTube for you."}
    - "Find my Python project" -> {"action": "tool", "app": "filesystem", "capability": "search_files", "params": {"pattern": "*.py", "directory": "~"}, "response": "Searching your file system."}
    - "Show my repositories" -> {"action": "tool", "app": "github", "capability": "list_repos", "params": {}, "response": "Fetching your repositories, Sir."}
    - "Find my resume in Google Drive" -> {"action": "tool", "app": "google", "capability": "search_drive", "params": {"query": "resume"}, "response": "Searching Google Drive."}
    Available convenience action names (use instead of "tool" for common tasks):
    spotify_open, spotify_search, spotify_play, spotify_pause, spotify_resume,
    spotify_next, spotify_previous, spotify_volume, spotify_current,
    spotify_playlist, spotify_add_to_playlist,
    browser_search, browser_open, browser_navigate, browser_click, browser_type,
    browser_scroll, browser_read, browser_screenshot, browser_find, browser_download,
    file_search, file_read, file_read_pdf, file_read_docx, file_read_xlsx,
    file_create, file_create_csv, file_create_folder, file_edit, file_delete,
    file_move, file_rename, file_open, file_convert, file_content_search, file_info,
    windows_screenshot, windows_clipboard, windows_brightness, windows_wifi,
    windows_bluetooth, windows_battery, windows_monitor, windows_minimize,
    windows_maximize, windows_switch, windows_volume,
    youtube_search, youtube_play, youtube_open, youtube_info, youtube_pause,
    youtube_next, youtube_previous,
    github_repos, github_search, github_create_repo, github_issues,
    github_create_issue, github_commits, github_create_branch, github_create_pr,
    google_drive_search, google_meetings, google_create_event, google_gmail_search,
    google_draft_email,
    discord_read, discord_channels, discord_search, app_discover.
    For destructive or sensitive actions (delete file, send email, send Discord
    message), set the confirmation flag: "confirm": true in params only after
    the user has explicitly approved the action.

AVAILABLE APPLICATIONS & CAPABILITIES (inspect then choose the right tool):
{capabilities}

CREDENTIAL STATUS:
{credentials}

IMPORTANT: Output ONLY the raw JSON object. Do not include markdown code block syntax or extra commentary.
"""

def build_system_function_calling_prompt() -> str:
    """Builds the dynamic system prompt with the live capability registry."""
    return (
        SYSTEM_FUNCTION_CALLING_PROMPT
        .replace("{capabilities}", capability_summary_text())
        .replace("{credentials}", credential_status_text())
    )

def extract_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Robust JSON extractor: handles raw JSON, markdown-wrapped JSON, and embedded JSON objects.
    """
    if not raw_text or not raw_text.strip():
        return None
        
    cleaned = raw_text.strip()
    
    # Remove markdown codeblock ```json ... ```
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find JSON block {...}
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    return None

def fallback_intent_extractor(prompt: str) -> Dict[str, Any]:
    """
    Rule-based semantic parser used as instant fallback when Ollama is offline or generates non-JSON.
    """
    p = prompt.strip().lower()

    # 0a. Spotify playback control
    if any(k in p for k in ["pause the music", "pause spotify", "pause the song", "pause music", "stop spotify", "stop the music", "stop music"]):
        return {"action": "spotify_pause", "response": "Pausing Spotify, Sir."}
    if any(k in p for k in ["resume spotify", "resume the music", "resume music", "continue playing", "play again"]):
        return {"action": "spotify_resume", "response": "Resuming your music, Sir."}
    if any(k in p for k in ["skip this song", "skip the song", "skip track", "next song", "next track", "skip song"]):
        return {"action": "spotify_next", "response": "Skipping to the next track."}
    if any(k in p for k in ["previous song", "previous track", "play the previous song", "go back a song", "go to previous song"]):
        return {"action": "spotify_previous", "response": "Going back to the previous track."}
    if any(k in p for k in ["what song is playing", "what's playing", "whats playing", "currently playing", "which song is playing"]):
        return {"action": "spotify_current", "response": "Let me check what is playing, Sir."}

    # 0b. Spotify play / playlist / search / volume
    playlist_match = re.search(r"^play\s+(?:my\s+|the\s+)?([a-z0-9 ]+?)\s+playlist", p)
    if playlist_match:
        return {"action": "spotify_playlist", "playlist_name": playlist_match.group(1).strip(), "response": f"Playing your '{playlist_match.group(1).strip()}' playlist."}
    if " spotify" in p and ("play " in p):
        query = re.sub(r"^(play|search for|search)\s+", "", p.replace(" on spotify", " ").replace(" spotify", " "))
        query = re.sub(r"\s+by\s+(.+)$", r" \1", query).strip()
        if query:
            return {"action": "spotify_play", "query": query, "response": f"Playing '{query}' on Spotify."}
    if "spotify" in p and ("search" in p):
        match = re.search(r"search(?: spotify)? for (.+)", p.replace(" on spotify", ""))
        if match:
            return {"action": "spotify_search", "query": match.group(1).strip(), "response": f"Searching Spotify for '{match.group(1).strip()}'."}
    spot_vol = re.search(r"(?:set\s+)?spotify\s+volume\s+(?:to\s+)?(\d+)", p)
    if spot_vol:
        return {"action": "spotify_volume", "level": int(spot_vol.group(1)), "response": f"Setting Spotify volume to {spot_vol.group(1)}%."}

    # 0c. System volume control
    sys_vol = re.search(r"set(?: the)? volume to (\d+)", p)
    if sys_vol:
        return {"action": "set_volume", "level": int(sys_vol.group(1)), "response": f"Setting volume to {sys_vol.group(1)} percent, Sir."}
    if any(k in p for k in ["increase volume", "volume up", "turn up the volume"]):
        return {"action": "volume_up", "step": 10, "response": "Increasing the volume."}
    if any(k in p for k in ["decrease volume", "volume down", "turn down the volume", "lower the volume"]):
        return {"action": "volume_down", "step": 10, "response": "Decreasing the volume."}
    if any(k in p for k in ["mute", "silence the audio", "mute volume"]):
        return {"action": "mute_volume", "response": "Muting the audio."}

    # 0d. YouTube
    if "youtube" in p and any(k in p for k in ["search", "find"]):
        query = re.sub(r"^(?:search|find)\s+(?:youtube)?\s*(?:for\s+)?", "", p.replace(" on youtube", "").replace(" youtube", "").strip())
        query = re.sub(r"\s+youtube$", "", query).strip()
        if query:
            return {"action": "youtube_search", "query": query, "response": f"Searching YouTube for '{query}'."}
    if "youtube" in p and "play" in p:
        query = re.sub(r"^(play|open)\s+", "", p.replace(" on youtube", "").replace(" youtube", "").strip())
        if query:
            return {"action": "youtube_play", "query": query, "response": f"Playing '{query}' on YouTube, Sir."}
    if p in ("open youtube", "go to youtube", "launch youtube"):
        return {"action": "open_url", "url": "https://www.youtube.com", "response": "Opening YouTube."}

    # 0e. Plain "play X" defaults to Spotify playback (per the integration spec)
    if p.startswith("play "):
        query = re.sub(r"^play\s+", "", p, flags=re.IGNORECASE).strip()
        query = re.sub(r"\s+by\s+(.+)$", r" \1", query).strip()
        if query:
            return {"action": "spotify_play", "query": query, "response": f"Playing '{query}' on Spotify, Sir."}

    # 0e. GitHub
    if any(k in p for k in ["show my repositories", "list my repositories", "show my repos", "list my repos", "my repositories", "my repos"]):
        return {"action": "github_repos", "response": "Fetching your repositories, Founder Prajjwal."}
    gh_user = re.search(r"show (.+) (?:repos|repositories)", p)
    if gh_user:
        return {"action": "github_repos", "username": gh_user.group(1).strip(), "response": f"Fetching repositories for {gh_user.group(1).strip()}."}
    gh_search = re.search(r"(?:search|find) repositories? for (.+)", p)
    if gh_search:
        return {"action": "github_search", "query": gh_search.group(1).strip(), "response": f"Searching GitHub for '{gh_search.group(1).strip()}'."}
    gh_create = re.search(r"create (?:a |new )?repository (?:called )?(?:named )?(.+)", p)
    if gh_create:
        return {"action": "github_create_repo", "name": gh_create.group(1).strip().replace(" ", "-").lower(), "response": f"Creating repository {gh_create.group(1).strip()}."}
    gh_issues = re.search(r"(?:list|show|get) issues? (?:in|for) ([a-zA-Z0-9_\-/]+)", p)
    if gh_issues:
        return {"action": "github_issues", "repo": gh_issues.group(1).strip(), "response": f"Fetching issues for {gh_issues.group(1).strip()}."}
    gh_commits = re.search(r"(?:show|list) commits? (?:in|for) ([a-zA-Z0-9_\-/]+)", p)
    if gh_commits:
        return {"action": "github_commits", "repo": gh_commits.group(1).strip(), "response": f"Fetching commits for {gh_commits.group(1).strip()}."}

    # 0f. File system patterns
    pdf_find = re.search(r"find (?:all |any )?pdfs|find pdf files", p)
    if pdf_find:
        return {"action": "file_search", "pattern": "**/*.pdf", "directory": "~", "response": "Searching for PDF files, Sir."}
    find_pattern = re.search(r"find (?:all |any )?(.+?) files?", p)
    if find_pattern:
        return {"action": "file_search", "pattern": f"**/*{find_pattern.group(1).strip()}*", "response": f"Searching for files matching '{find_pattern.group(1).strip()}'."}
    file_dispatch = re.search(r"^(?:read|open)\s+(?:the\s+)?([\w\- .\\/~]+\.(?:pdf|docx?|xlsx?|csv|txt|json|pptx|zip))$", p)
    if file_dispatch:
        name = file_dispatch.group(1).strip()
        ext = name.rsplit(".", 1)[-1].lower()
        action_for_ext = {
            "pdf": "file_read_pdf", "docx": "file_read_docx", "doc": "file_read_docx",
            "xlsx": "file_read_xlsx", "xls": "file_read_xlsx", "csv": "file_read_csv",
            "json": "file_read_json", "txt": "file_read", "pptx": "file_read_pptx", "zip": "file_read_zip",
        }
        if p.startswith("open "):
            return {"action": "file_open", "path": name, "response": f"Opening {name}."}
        return {"action": action_for_ext.get(ext, "file_read"), "path": name, "response": f"Reading {name}."}

    # 0g. Windows control
    if any(k in p for k in ["take a screenshot", "take screenshot", "capture screen", "screenshot of screen"]):
        return {"action": "windows_screenshot", "response": "Taking a screenshot, Sir."}
    copy_match = re.search(r"copy (?:this |the )?(?:text )?['\"](.+?)['\"] to clipboard|copy ['\"](.+?)['\"]", p)
    if copy_match:
        return {"action": "windows_clipboard", "text": copy_match.group(1) or copy_match.group(2), "response": "Copied to clipboard."}
    if any(k in p for k in ["clipboard content", "what is on the clipboard", "what's on the clipboard"]):
        return {"action": "windows_clipboard_get", "response": "Reading the clipboard."}
    if "wifi" in p and any(k in p for k in ["status", "connected", "on"]):
        return {"action": "windows_wifi", "response": "Checking Wi-Fi status."}
    if "bluetooth" in p and any(k in p for k in ["status", "enabled", "on"]):
        return {"action": "windows_bluetooth", "response": "Checking Bluetooth status."}
    if "battery" in p and any(k in p for k in ["status", "percent", "level", "how much"]):
        return {"action": "windows_battery", "response": "Checking the battery."}

    # 1. Close app
    if p.startswith("close ") or p.startswith("kill ") or p.startswith("quit ") or p.startswith("exit "):
        target = re.sub(r"^(close|kill|quit|exit)\s+", "", p).strip()
        return {
            "action": "close_app",
            "target": target,
            "response": f"Closing {target.capitalize()}."
        }

    # 2. Open app
    if p.startswith("open ") or p.startswith("launch ") or p.startswith("start "):
        target = re.sub(r"^(open|launch|start)\s+", "", p).strip()
        # Check if URL
        if target.startswith("http") or target.startswith("www.") or ".com" in target or ".org" in target:
            return {
                "action": "open_url",
                "url": target,
                "response": f"Opening {target}."
            }
        return {
            "action": "open_app",
            "target": target,
            "response": f"Opening {target.capitalize()} for you."
        }

    # 3. Lock screen
    if any(k in p for k in ["lock screen", "lock computer", "lock pc", "lock workstation"]):
        return {
            "action": "lock_screen",
            "response": "Locking your computer screen now."
        }

    # 4. Telemetry / Diagnostics
    if any(k in p for k in ["system specs", "telemetry", "cpu usage", "ram usage", "memory usage", "battery status", "diagnostics", "system status"]):
        return {
            "action": "system_telemetry",
            "response": "Here is your system telemetry."
        }

    # 5. Web Search
    search_match = re.search(r"^(search|google|lookup)\s+(for\s+)?(.+)", p)
    if search_match:
        query = search_match.group(3).strip()
        return {
            "action": "web_search",
            "query": query,
            "response": f"Searching Google for {query}."
        }

    # 6. Default conversation
    return {
        "action": "chat",
        "response": f"I received your request: '{prompt}'. All local system tools and actions are ready."
    }

def query_ollama_structured(prompt: str, history: List[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Sends prompt to Ollama requesting structured JSON output (using format='json').
    """
    config = load_config()
    ip = config.get("partner_ip", "192.168.31.48")
    port = config.get("ollama_port", 11434)
    model = config.get("ollama_model", "MyCustomAI")
    
    url = f"http://{ip}:{port}/api/chat"
    
    messages = [{"role": "system", "content": build_system_function_calling_prompt()}]
    if history:
        messages.extend(history[-4:])
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 256
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=(1.2, 3.0))
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            return extract_json_payload(content)
    except Exception:
        pass
        
    # Fallback /api/generate
    gen_url = f"http://{ip}:{port}/api/generate"
    gen_payload = {
        "model": model,
        "system": build_system_function_calling_prompt(),
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    try:
        resp = requests.post(gen_url, json=gen_payload, timeout=(1.2, 3.0))
        if resp.status_code == 200:
            content = resp.json().get("response", "")
            return extract_json_payload(content)
    except Exception:
        pass

    return None

# ==========================================================
# REGISTERED CAPABILITY DISPATCH (principles #2 & #3)
# Maps convenience action names / payload fields to (app, capability, param_keys).
# ==========================================================
TOOL_ACTION_MAP = {
    # ----- Spotify -----
    "spotify_open": ("spotify", "open", []),
    "spotify_search": ("spotify", "search", ["query", "limit"]),
    "spotify_play": ("spotify", "play", ["query", "uri"]),
    "spotify_playlist": ("spotify", "play_playlist", ["playlist_name", "playlist_uri"]),
    "spotify_pause": ("spotify", "pause", []),
    "spotify_resume": ("spotify", "resume", []),
    "spotify_next": ("spotify", "next", []),
    "spotify_previous": ("spotify", "previous", []),
    "spotify_volume": ("spotify", "volume", ["level", "device_id"]),
    "spotify_shuffle": ("spotify", "shuffle", ["on"]),
    "spotify_current": ("spotify", "current_track", []),
    "spotify_playback_state": ("spotify", "playback_state", []),
    "spotify_devices": ("spotify", "get_devices", []),
    "spotify_playlists": ("spotify", "playlists", ["limit"]),
    "spotify_add_to_playlist": ("spotify", "add_track_to_playlist", ["track_uri", "query", "playlist_name", "playlist_uri"]),
    # ----- Browser -----
    "browser_search": ("browser", "search_web", ["query", "engine", "num_results"]),
    "browser_open": ("browser", "open_url", ["url", "new_tab"]),
    "browser_open_url": ("browser", "open_url", ["url", "new_tab"]),
    "browser_navigate": ("browser", "open_url", ["url", "new_tab"]),
    "browser_click": ("browser", "click", ["selector"]),
    "browser_click_text": ("browser", "click_link_by_text", ["text"]),
    "browser_type": ("browser", "type", ["selector", "text", "submit"]),
    "browser_scroll": ("browser", "scroll", ["direction", "amount"]),
    "browser_read": ("browser", "read_webpage_text", ["url", "max_chars"]),
    "browser_find": ("browser", "find_text", ["text"]),
    "browser_screenshot": ("browser", "screenshot", ["destination"]),
    "browser_download": ("browser", "download_file", ["url", "destination"]),
    "browser_upload": ("browser", "upload_file", ["selector", "file_path"]),
    "browser_page_state": ("browser", "page_state", []),
    "browser_get_links": ("browser", "get_links", ["max_links"]),
    # ----- File System -----
    "file_search": ("filesystem", "search_files", ["pattern", "directory", "recursive"]),
    "file_list": ("filesystem", "list_directory", ["directory", "show_hidden"]),
    "file_read": ("filesystem", "read_file", ["path", "max_chars"]),
    "file_read_pdf": ("filesystem", "read_pdf", ["path", "max_pages"]),
    "file_read_docx": ("filesystem", "read_docx", ["path"]),
    "file_read_xlsx": ("filesystem", "read_xlsx", ["path", "sheet"]),
    "file_read_csv": ("filesystem", "read_csv", ["path", "delimiter"]),
    "file_read_json": ("filesystem", "read_json", ["path"]),
    "file_read_pptx": ("filesystem", "read_pptx", ["path"]),
    "file_create": ("filesystem", "create_file", ["path", "content", "overwrite", "confirm"]),
    "file_create_csv": ("filesystem", "create_csv", ["path", "rows", "headers", "delimiter"]),
    "file_create_folder": ("filesystem", "create_folder", ["path"]),
    "file_edit": ("filesystem", "edit_file", ["path", "new_content", "replace", "replacement", "append", "confirm"]),
    "file_delete": ("filesystem", "delete_file", ["path", "confirm"]),
    "file_move": ("filesystem", "move_file", ["source", "destination", "confirm"]),
    "file_rename": ("filesystem", "rename_file", ["path", "new_name", "confirm"]),
    "file_open": ("filesystem", "open_file", ["path"]),
    "file_convert": ("filesystem", "convert_file", ["source", "target_format", "destination"]),
    "file_content_search": ("filesystem", "search_inside_files", ["term", "directory", "extensions", "max_results"]),
    "file_info": ("filesystem", "get_file_info", ["path"]),
    # ----- Windows -----
    "windows_screenshot": ("windows", "screenshot", ["destination"]),
    "windows_clipboard": ("windows", "clipboard_set", ["text"]),
    "windows_clipboard_get": ("windows", "clipboard_get", []),
    "windows_brightness": ("windows", "set_brightness", ["level"]),
    "windows_wifi": ("windows", "wifi_status", []),
    "windows_bluetooth": ("windows", "bluetooth_status", []),
    "windows_battery": ("windows", "battery_info", []),
    "windows_monitor": ("windows", "monitor_cpu_ram", []),
    "windows_minimize": ("windows", "minimize_window", ["title"]),
    "windows_maximize": ("windows", "maximize_window", ["title"]),
    "windows_switch": ("windows", "switch_windows", ["title"]),
    "windows_foreground": ("windows", "foreground_window", []),
    "windows_volume": ("windows", "set_volume", ["level"]),
    "windows_volume_get": ("windows", "get_volume", []),
    "windows_type": ("windows", "keyboard_input", ["text"]),
    "windows_press": ("windows", "press_key", ["key"]),
    "windows_hotkey": ("windows", "hotkey", ["keys"]),
    "windows_mouse_move": ("windows", "mouse_move", ["x", "y", "absolute"]),
    "windows_mouse_click": ("windows", "mouse_click", ["x", "y", "button", "double"]),
    # ----- YouTube -----
    "youtube_search": ("youtube", "search_videos", ["query", "limit", "max_duration_minutes"]),
    "youtube_channel": ("youtube", "search_channel", ["query", "limit"]),
    "youtube_playlist_search": ("youtube", "search_playlist", ["query", "limit"]),
    "youtube_play": ("youtube", "play", ["query", "video_url"]),
    "youtube_open": ("youtube", "open_video", ["video_id", "video_url", "query"]),
    "youtube_info": ("youtube", "get_video_info", ["video_id"]),
    "youtube_pause": ("youtube", "pause", []),
    "youtube_next": ("youtube", "next", []),
    "youtube_previous": ("youtube", "previous", []),
    # ----- GitHub -----
    "github_user": ("github", "get_user", ["username"]),
    "github_repos": ("github", "list_repos", ["username", "sort"]),
    "github_repo": ("github", "get_repository", ["repo"]),
    "github_search": ("github", "search_repos", ["query", "limit"]),
    "github_create_repo": ("github", "create_repo", ["name", "description", "private", "auto_init"]),
    "github_issues": ("github", "list_issues", ["repo", "state", "limit"]),
    "github_create_issue": ("github", "create_issue", ["repo", "title", "body", "labels"]),
    "github_issue": ("github", "get_issue", ["repo", "number"]),
    "github_commits": ("github", "list_commits", ["repo", "branch", "limit"]),
    "github_branches": ("github", "list_branches", ["repo", "limit"]),
    "github_create_branch": ("github", "create_branch", ["repo", "branch", "from_branch"]),
    "github_create_pr": ("github", "create_pr", ["repo", "title", "head", "base", "body"]),
    "github_prs": ("github", "list_pull_requests", ["repo", "state", "limit"]),
    # ----- Google -----
    "google_drive_search": ("google", "search_drive", ["query", "limit"]),
    "google_drive_find": ("google", "find_drive_file", ["name"]),
    "google_meetings": ("google", "today_meetings", []),
    "google_create_event": ("google", "create_calendar_event", ["summary", "start_time", "end_time", "duration_minutes", "description", "location"]),
    "google_gmail_search": ("google", "search_gmail", ["query", "limit"]),
    "google_draft_email": ("google", "draft_email", ["to", "subject", "body"]),
    "google_send_email": ("google", "send_email", ["to", "subject", "body", "confirm"]),
    # ----- Discord -----
    "discord_read": ("discord", "read_messages", ["channel", "guild_id", "limit"]),
    "discord_channels": ("discord", "list_channels", ["guild_id"]),
    "discord_search": ("discord", "search_messages", ["query", "guild_id", "limit"]),
    "discord_send": ("discord", "send_message", ["channel", "content", "guild_id", "confirm"]),
    # ----- App Launcher -----
    "app_discover": ("app_launcher", "discover_apps", ["query", "limit"]),
    "app_check": ("app_launcher", "is_app_installed", ["app_name"]),
}


def _dispatch_registered_tool(action_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Executes a convenience action through the integration dispatcher."""
    entry = TOOL_ACTION_MAP.get(action_type)
    if not entry:
        return None
    app_key, capability, param_keys = entry
    params = {key: payload.get(key) for key in param_keys if payload.get(key) is not None}
    return execute_tool(app_key, capability, params)


def execute_structured_action(action_payload: Dict[str, Any], auto_execute: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Dispatches parsed JSON action to the corresponding native executor.
    Returns: (spoken_text, executed_actions_list)
    """
    action_type = action_payload.get("action", "chat")
    spoken_response = action_payload.get("response", "")
    actions_executed = []

    if not auto_execute and action_type != "chat":
        return spoken_response or "Action pending approval.", [{
            "action_type": action_type,
            "status": "pending_approval",
            "payload": action_payload,
            "timestamp": datetime.now().isoformat()
        }]

    # 1. Open App
    if action_type == "open_app":
        target = action_payload.get("target", "")
        res = launch_application(target)
        actions_executed.append({
            "action_type": "open_app",
            "command": f"launch {target}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "details": res,
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = res.get("output") or f"Could not launch {target}."

    # 2. Close App
    elif action_type == "close_app":
        target = action_payload.get("target", "")
        res = close_application(target)
        actions_executed.append({
            "action_type": "close_app",
            "command": f"close {target}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "details": res,
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = res.get("output") or f"Could not close {target}."

    # 3. Lock Screen
    elif action_type == "lock_screen":
        res = lock_workstation()
        actions_executed.append({
            "action_type": "lock_screen",
            "command": "lock_screen",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = "Locking your screen."

    # 4. Telemetry
    elif action_type == "system_telemetry":
        telemetry_res = get_detailed_telemetry()
        actions_executed.append({
            "action_type": "system_telemetry",
            "command": "get_telemetry",
            "status": "success",
            "output": telemetry_res["summary"],
            "telemetry": telemetry_res,
            "timestamp": datetime.now().isoformat()
        })
        spoken_response = f"System telemetry: {telemetry_res['summary']}"

    # 5. Web Search
    elif action_type == "web_search":
        query = action_payload.get("query", "")
        res = execute_web_search(query)
        actions_executed.append({
            "action_type": "web_search",
            "command": f"search {query}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = f"Searching Google for {query}."

    # 6. Open URL
    elif action_type == "open_url":
        url = action_payload.get("url", "")
        res = execute_open_url(url)
        actions_executed.append({
            "action_type": "open_url",
            "command": f"open {url}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = f"Opening {url}."

    # 7. Shell Command
    elif action_type == "shell_command":
        cmd = action_payload.get("command", "")
        res = execute_shell_task(cmd)
        actions_executed.append({
            "action_type": "shell_command",
            "command": cmd,
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "return_code": res.get("return_code", 0),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = "Executed shell command."

    # 8. System Volume Control (native)
    elif action_type == "volume_up":
        step = int(action_payload.get("step", 10))
        res = increase_volume(step)
        actions_executed.append({"action_type": "volume_up", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or "Increasing volume."
    elif action_type == "volume_down":
        step = int(action_payload.get("step", 10))
        res = decrease_volume(step)
        actions_executed.append({"action_type": "volume_down", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or "Decreasing volume."
    elif action_type == "set_volume":
        level = int(action_payload.get("level", 50))
        res = set_volume(level)
        actions_executed.append({"action_type": "set_volume", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or f"Setting volume to {level}%."
    elif action_type == "mute_volume":
        res = mute_volume()
        actions_executed.append({"action_type": "mute_volume", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or "Muting audio."

    # 9. Legacy YouTube action
    elif action_type == "play_youtube":
        query = action_payload.get("query", "")
        res = play_youtube(query)
        actions_executed.append({"action_type": "play_youtube", "command": f"play {query}", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or f"Playing {query} on YouTube."

    # 10. Legacy code generation
    elif action_type == "write_code":
        desc = action_payload.get("description", "")
        language = action_payload.get("language", "python")
        filename = action_payload.get("filename")
        res = generate_and_open_code(desc, filename=filename, language=language)
        actions_executed.append({"action_type": "write_code", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or "Generating code."

    # 11. Legacy file read / write
    elif action_type == "read_file":
        filepath = action_payload.get("filepath", "")
        res = read_text_file(filepath)
        actions_executed.append({"action_type": "read_file", "command": f"read {filepath}", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "filepath": res.get("filepath"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or f"Read {filepath}."
    elif action_type == "write_file":
        filename = action_payload.get("filename", "")
        content = action_payload.get("content", "")
        res = create_text_file(filename, content)
        actions_executed.append({"action_type": "write_file", "command": f"write {filename}", "status": "success" if res.get("success") else "error", "output": res.get("output") or res.get("error"), "timestamp": datetime.now().isoformat()})
        spoken_response = spoken_response or res.get("output") or f"Created {filename}."

    # 12. Generic registered-capability dispatch (design principle #3)
    elif action_type == "tool":
        app_key = action_payload.get("app", "")
        capability = action_payload.get("capability", "")
        params = action_payload.get("params") or {}
        res = execute_tool(app_key, capability, params)
        actions_executed.append({
            "action_type": f"{app_key}.{capability}",
            "app": app_key,
            "capability": capability,
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "details": res,
            "timestamp": datetime.now().isoformat()
        })
        spoken_response = spoken_response or res.get("output") or res.get("error") or f"Executed {capability} on {app_key}."

    # 13. Chat fallback (with convenience-tool detection)
    else:
        dispatch_res = _dispatch_registered_tool(action_type, action_payload)
        if dispatch_res is not None:
            res = dispatch_res
            actions_executed.append({
                "action_type": action_type,
                "status": "success" if res.get("success") else "error",
                "output": res.get("output") or res.get("error"),
                "details": res,
                "timestamp": datetime.now().isoformat()
            })
            spoken_response = spoken_response or res.get("output") or res.get("error") or "Executed action."
        elif not spoken_response:
            spoken_response = action_payload.get("text", "Understood.")

    return spoken_response, actions_executed

def process_function_calling_turn(prompt: str, history: List[Dict[str, str]] = None, auto_execute: bool = True) -> Dict[str, Any]:
    """
    Main entry point:
    1. Queries Ollama for structured JSON action.
    2. Falls back to semantic intent parser if needed.
    3. Executes the structured action natively on Windows.
    """
    # 1. Try Ollama JSON Function Calling
    json_payload = query_ollama_structured(prompt, history)
    source = "ollama_json"
    
    # 2. Fallback to semantic rules
    if not json_payload:
        json_payload = fallback_intent_extractor(prompt)
        source = "rule_engine"

    # 3. Execute action
    spoken_text, actions = execute_structured_action(json_payload, auto_execute=auto_execute)

    return {
        "text": spoken_text,
        "spoken_text": spoken_text,
        "json_payload": json_payload,
        "actions": actions,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }

"""
Tool Dispatcher
Resolves (application, capability) -> concrete tool function and executes it.
The single entry point the agent (rule engine or LLM structured action schema)
uses to run any capability registered in `app.integrations.registry`.

execute_tool(app_key, capability, params) -> result dict
"""

from typing import Dict, Any, Optional, Callable

from app.integrations import registry  # noqa: F401  (imports side effects of registry)
from app.integrations.registry import has_capability, get_application

# Lazy imports avoid heavy dependency loading at import time (e.g. Playwright).
def _load_tool_map() -> Dict[str, Dict[str, Callable[..., Dict[str, Any]]]]:
    from app.integrations import spotify, browser, file_system, windows_control, app_launcher, youtube, github, google, discord, context

    return {
        "spotify": {
            "open": spotify.open_spotify,
            "search": spotify.search_spotify,
            "play": spotify.play_spotify,
            "play_playlist": spotify.play_playlist,
            "pause": spotify.pause_spotify,
            "resume": spotify.resume_spotify,
            "next": spotify.next_track,
            "previous": spotify.previous_track,
            "volume": spotify.set_volume,
            "shuffle": spotify.shuffle,
            "current_track": spotify.get_current_track,
            "playback_state": spotify.get_playback_state,
            "playlists": spotify.get_playlists,
            "add_track_to_playlist": spotify.add_track_to_playlist,
            "get_devices": spotify.get_devices,
            "authenticate": spotify.authenticate_spotify,
        },
        "browser": {
            "open": browser.open_browser,
            "open_url": browser.open_url,
            "search_web": browser.search_web,
            "find_text": browser.find_text,
            "click": browser.click_element,
            "click_link_by_text": browser.click_link_by_text,
            "type": browser.type_text,
            "scroll": browser.scroll_page,
            "read_webpage_text": browser.read_webpage_text,
            "download_file": browser.download_file,
            "upload_file": browser.upload_file,
            "screenshot": browser.take_screenshot,
            "page_state": browser.page_state,
            "get_links": browser.get_links,
            "close": browser.close_browser,
        },
        "filesystem": {
            "search_files": file_system.search_files,
            "list_directory": file_system.list_directory,
            "search_inside_files": file_system.search_inside_files,
            "get_file_info": file_system.get_file_info,
            "read_file": file_system.read_file,
            "read_pdf": file_system.read_pdf,
            "read_docx": file_system.read_docx,
            "read_xlsx": file_system.read_xlsx,
            "read_csv": file_system.read_csv,
            "read_json": file_system.read_json,
            "read_pptx": file_system.read_pptx,
            "read_zip": file_system.read_zip,
            "create_file": file_system.create_file,
            "create_csv": file_system.create_csv,
            "create_folder": file_system.create_folder,
            "edit_file": file_system.edit_file,
            "delete_file": file_system.delete_file,
            "move_file": file_system.move_file,
            "rename_file": file_system.rename_file,
            "open_file": file_system.open_file,
            "convert_file": file_system.convert_file,
        },
        "windows": {
            "foreground_window": windows_control.foreground_window,
            "list_windows": windows_control.list_windows,
            "minimize_window": windows_control.minimize_window,
            "maximize_window": windows_control.maximize_window,
            "restore_window": windows_control.restore_window,
            "switch_windows": windows_control.switch_windows,
            "screenshot": windows_control.take_screenshot,
            "keyboard_input": windows_control.type_text,
            "press_key": windows_control.press_key,
            "hotkey": windows_control.hotkey,
            "mouse_move": windows_control.mouse_move,
            "mouse_click": windows_control.mouse_click,
            "mouse_scroll": windows_control.mouse_scroll,
            "clipboard_set": windows_control.clipboard_set,
            "clipboard_get": windows_control.clipboard_get,
            "set_volume": windows_control.set_volume,
            "get_volume": windows_control.get_volume,
            "adjust_volume": windows_control.adjust_volume,
            "get_brightness": windows_control.get_brightness,
            "set_brightness": windows_control.set_brightness,
            "wifi_status": windows_control.wifi_status,
            "bluetooth_status": windows_control.bluetooth_status,
            "battery_info": windows_control.battery_info,
            "monitor_cpu_ram": windows_control.monitor_cpu_ram,
            "get_location": context.get_user_location,
        },
        "app_launcher": {
            "discover_apps": app_launcher.discover_apps,
            "open_application": app_launcher.open_application,
            "close_application": app_launcher.close_application,
            "is_app_installed": app_launcher.is_app_installed,
            "suggest_paths": app_launcher.suggest_paths,
        },
        "youtube": {
            "search_videos": youtube.search_videos,
            "search_channel": youtube.search_channel,
            "search_playlist": youtube.search_playlist,
            "get_video_info": youtube.get_video_info,
            "open_video": youtube.open_video,
            "play": youtube.play,
            "pause": youtube.pause,
            "next": youtube.next_video,
            "previous": youtube.previous_video,
        },
        "github": {
            "get_user": github.get_user,
            "list_repos": github.list_repos,
            "get_repository": github.get_repository,
            "create_repo": github.create_repo,
            "create_issue": github.create_issue,
            "list_issues": github.list_issues,
            "get_issue": github.get_issue,
            "create_branch": github.create_branch,
            "list_branches": github.list_branches,
            "list_commits": github.list_commits,
            "create_pr": github.create_pr,
            "list_pull_requests": github.list_pull_requests,
            "search_repos": github.search_repos,
        },
        "google": {
            "search_drive": google.search_drive,
            "find_drive_file": google.find_drive_file,
            "create_calendar_event": google.create_calendar_event,
            "today_meetings": google.today_meetings,
            "search_gmail": google.search_gmail,
            "draft_email": google.draft_email,
            "send_email": google.send_email,
        },
        "discord": {
            "get_bot_info": discord.get_bot_info,
            "get_guilds": discord.get_guilds,
            "list_channels": discord.list_channels,
            "get_channel_info": discord.get_channel_info,
            "read_messages": discord.read_messages,
            "search_messages": discord.search_messages,
            "send_message": discord.send_message,
        },
    }


# Cached tool map (built lazily once).
_tool_map: Optional[Dict[str, Dict[str, Callable[..., Dict[str, Any]]]]] = None


def tool_map() -> Dict[str, Dict[str, Callable[..., Dict[str, Any]]]]:
    global _tool_map
    if _tool_map is None:
        _tool_map = _load_tool_map()
    return _tool_map


def get_tool(app_key: str, capability: str) -> Optional[Callable[..., Dict[str, Any]]]:
    """Returns the callable for (app, capability), or None."""
    if not has_capability(app_key, capability):
        return None
    return tool_map().get(app_key, {}).get(capability)


def list_tools() -> Dict[str, Any]:
    """Returns the full (app -> [capabilities -> function]) inventory."""
    result = {}
    for app_key, caps in tool_map().items():
        result[app_key] = {
            cap: getattr(fn, "__name__", repr(fn)) for cap, fn in caps.items() if has_capability(app_key, cap)
        }
    return result


def execute_tool(app_key: str, capability: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Executes a capability on an application.
    - Returns {"success": False, "error": ...} for unknown apps/capabilities.
    - Passes only keyword arguments relevant to the target function.
    """
    app = get_application(app_key)
    if not app:
        return {"success": False, "error": f"Unknown application '{app_key}'.", "known_apps": list(registry.APPLICATIONS.keys())}
    if not has_capability(app_key, capability):
        return {
            "success": False,
            "error": f"Application '{app_key}' does not expose capability '{capability}'.",
            "available_capabilities": app["capabilities"],
        }
    fn = get_tool(app_key, capability)
    if fn is None:
        return {"success": False, "error": f"Tool for '{app_key}.{capability}' is not implemented in the dispatcher."}
    kwargs = dict(params or {})

    # Only pass arguments the function actually accepts.
    import inspect
    signature = inspect.signature(fn)
    valid = {}
    for name, value in kwargs.items():
        if name in signature.parameters:
            valid[name] = value
        elif any(p.kind == inspect.Parameter.VAR_KEYWORD for p in signature.parameters.values()):
            valid[name] = value

    try:
        return fn(**valid)
    except TypeError as e:
        return {"success": False, "error": f"Invalid arguments for '{app_key}.{capability}': {e}", "params": valid}
    except Exception as e:
        return {"success": False, "app": app_key, "capability": capability, "error": str(e)}


def execute_by_phrase(phrase: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Resolves a human phrase like "open spotify" or "browser.search_web"
    to a (app, capability) and executes it.
    """
    phrase = phrase.strip().lower()
    if "." in phrase:
        app_key, capability = phrase.split(".", 1)
        if has_capability(app_key, capability):
            return execute_tool(app_key, capability, params)
        return {"success": False, "error": f"Unknown capability '{capability}' on '{app_key}'."}

    # Try exact capability matches across all apps.
    for candidate in registry.APPLICATIONS:
        if phrase == candidate:
            return {"success": False, "error": f"'{phrase}' is an app, not a capability. Use a capability like '{list(registry.APPLICATIONS[candidate]['capabilities'])[0]}'."}
        if phrase in registry.APPLICATIONS[candidate]["capabilities"]:
            return execute_tool(candidate, phrase, params)

    # Fuzzy phrase -> (app.capability)
    for app_key, entry in registry.APPLICATIONS.items():
        for cap in entry["capabilities"]:
            token = cap.replace("_", " ")
            if token == phrase:
                return execute_tool(app_key, cap, params)
    return {"success": False, "error": f"Could not resolve '{phrase}' to any tool."}
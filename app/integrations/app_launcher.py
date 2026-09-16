"""
Application Launcher & Dynamic Discovery Subsystem
Wraps the native `app.core.app_launcher` and adds:
- Start-Menu (.lnk) scanning for discovering installed apps without hardcoding.
- Explanations + configuration hints when an app cannot be found.

Capabilities:
    discover_apps, open_application, close_application, is_app_installed, suggest_paths
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.app_launcher import (
    launch_application as _launch,
    close_application as _close,
    scan_windows_app_paths,
    KNOWN_APP_MAP,
)

START_MENU_PATHS = [
    Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
    Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
]

_startmenu_cache: Dict[str, str] = {}
_startmenu_scanned = False


def _scan_start_menu() -> Dict[str, str]:
    """Finds app names -> .lnk paths from the Start Menu (recursive)."""
    global _startmenu_cache, _startmenu_scanned
    if _startmenu_scanned:
        return _startmenu_cache
    found: Dict[str, str] = {}
    for base in START_MENU_PATHS:
        if not base.exists():
            continue
        for lnk in base.rglob("*.lnk"):
            stem = lnk.stem.lower()
            found[stem] = str(lnk)
            found[stem.replace(" ", "")] = str(lnk)
    _startmenu_cache = found
    _startmenu_scanned = True
    return found


def discover_apps(query: str = None, limit: int = 50) -> Dict[str, Any]:
    """Lists discovered applications (registry AppPaths + Start Menu shortcuts)."""
    apps: Dict[str, Any] = {}
    try:
        reg = scan_windows_app_paths()
        for name, path in reg.items():
            apps[name] = {"name": name, "source": "registry", "path": path}
    except Exception:
        pass
    for name, path in _scan_start_menu().items():
        apps.setdefault(name, {"name": name, "source": "start_menu", "path": path})

    names = sorted(apps.keys())
    if query:
        q = query.strip().lower()
        names = [n for n in names if q in n or q in apps[n]["path"].lower()]
    names = names[:limit]
    result = [apps[n] for n in names]
    return {"success": True, "apps": result, "count": len(result), "output": f"Discovered {len(result)} application(s)."}


def is_app_installed(app_name: str) -> Dict[str, Any]:
    """Checks whether an application is resolvable (aliases, registry, start menu)."""
    from app.core.app_launcher import resolve_application
    cmd, confidence, matched = resolve_application(app_name)
    start_menu = _scan_start_menu()
    in_start_menu = app_name.strip().lower() in start_menu or any(
        start_menu[k] for k in start_menu if app_name.strip().lower() in k
    )
    found = bool(cmd) and confidence >= 0.4
    return {
        "success": found or in_start_menu,
        "installed": found or in_start_menu,
        "matched_name": matched if found else None,
        "confidence": round(confidence, 2),
        "start_menu": in_start_menu,
        "output": f"'{app_name}' is installed." if (found or in_start_menu) else f"'{app_name}' was not found.",
    }


def open_application(app_name: str) -> Dict[str, Any]:
    """Opens an application by name (with dynamic discovery fallback)."""
    res = _launch(app_name)
    if res.get("success"):
        return {**res, "output": f"Successfully launched {app_name}."}
    # Try a Start Menu shortcut if the raw launch failed.
    lnk = _find_shortcut(app_name)
    if lnk:
        try:
            import subprocess
            subprocess.Popen([f'explorer "{lnk}"'], shell=True)
            return {"success": True, "target": app_name, "method": "start_menu", "shortcut": lnk, "output": f"Launched {app_name} via Start Menu shortcut."}
        except Exception as e:
            pass
    return _not_found_response(app_name, res)


def open_file_with_default_app(path: str) -> Dict[str, Any]:
    """Opens a file / folder with the default Windows application (os.startfile)."""
    try:
        os.startfile(path)  # type: ignore[attr-defined]
        return {"success": True, "path": path, "output": f"Opened '{path}' with the default application."}
    except Exception as e:
        return {"success": False, "error": f"Failed to open '{path}': {e}"}


def close_application(app_name: str) -> Dict[str, Any]:
    """Closes running instances of an application."""
    return _close(app_name)


def suggest_paths(app_name: str) -> Dict[str, Any]:
    """Explains why an app was not found and where to configure its path."""
    reg = scan_windows_app_paths()
    start_menu = _scan_start_menu()
    base_dirs = [
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("PROGRAMFILES(X86)", ""),
    ]
    suggestions = []
    try:
        for base in base_dirs:
            if not base or not os.path.isdir(base):
                continue
            base_path = Path(base)
            for candidate in _iter_candidate(base_path, app_name):
                suggestions.append(str(candidate))
    except Exception:
        pass
    return {
        "success": False,
        "message": (
            f"Could not find '{app_name}'. Common causes:\n"
            "1. The app is a portable/UWP app not registered in the Windows registry.\n"
            "2. It is installed for a different user or in a non-standard location.\n"
            "3. The app name differs from the executable name.\n\n"
            "To configure it manually, add an entry to KNOWN_APP_MAP in "
            "app/core/app_launcher.py or run 'open <full-path-to-exe>'."
        ),
        "suggested_locations": suggestions[:8],
        "registry_entries": list(reg.keys())[:10],
        "start_menu_count": len(start_menu),
    }


def _iter_candidate(base: Path, app_name: str):
    query = app_name.strip().lower()
    for exe in base.rglob("*.exe"):
        if query in exe.stem.lower() or query in exe.name.lower():
            yield exe


def _find_shortcut(app_name: str) -> Optional[str]:
    q = app_name.strip().lower()
    for name, path in _scan_start_menu().items():
        if q in name or name in q:
            return path
        if q in os.path.basename(path).lower():
            return path
    return None


def _not_found_response(app_name: str, original: Dict[str, Any]) -> Dict[str, Any]:
    hint = suggest_paths(app_name)
    return {
        "success": False,
        "target": app_name,
        "error": original.get("error") or f"Could not find or launch '{app_name}'.",
        "explanation": hint["message"],
        "suggested_locations": hint["suggested_locations"],
    }
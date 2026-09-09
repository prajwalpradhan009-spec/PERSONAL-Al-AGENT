"""
Native Windows Application Launcher & Process Automation Module
Provides fuzzy matching, Windows Registry AppPaths discovery, UWP integration, and process management.
"""

import os
import sys
import winreg
import difflib
import subprocess
import psutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Pre-mapped high-priority aliases for common applications
KNOWN_APP_MAP: Dict[str, str] = {
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "code": "code",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "browser": "start https://www.google.com",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "brave": "brave.exe",
    "firefox": "firefox.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "text editor": "notepad.exe",
    "spotify": "start spotify:",
    "music": "start spotify:",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "telegram": "telegram.exe",
    "terminal": "start wt.exe || start powershell.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "settings": "start ms-settings:",
    "windows settings": "start ms-settings:",
    "control panel": "control.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "steam": "steam.exe",
    "obs": "obs64.exe",
    "vlc": "vlc.exe",
}

# Cache for discovered registry applications
_registry_cache: Dict[str, str] = {}
_cache_initialized: bool = False

def scan_windows_app_paths() -> Dict[str, str]:
    """
    Scans Windows Registry for registered application executables under App Paths.
    Queries both HKEY_LOCAL_MACHINE and HKEY_CURRENT_USER.
    """
    global _registry_cache, _cache_initialized
    if _cache_initialized:
        return _registry_cache

    apps: Dict[str, str] = {}
    reg_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
    ]

    for root_key, sub_key in reg_keys:
        try:
            with winreg.OpenKey(root_key, sub_key) as key:
                num_subkeys = winreg.QueryInfoKey(key)[0]
                for i in range(num_subkeys):
                    try:
                        app_sub_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_sub_name) as app_key:
                            exe_path, _ = winreg.QueryValueEx(app_key, "")
                            if exe_path:
                                base_name = app_sub_name.lower().replace(".exe", "")
                                apps[base_name] = exe_path
                                apps[app_sub_name.lower()] = exe_path
                    except (OSError, WindowsError):
                        continue
        except (OSError, WindowsError):
            continue

    _registry_cache = apps
    _cache_initialized = True
    return _registry_cache

def resolve_application(target_name: str) -> Tuple[Optional[str], float, str]:
    """
    Resolves an application name to an executable or launch command using exact and fuzzy matching.
    Returns: (executable_path_or_command, confidence_score, resolved_name)
    """
    clean_target = target_name.strip().lower()
    
    # 1. Exact match in predefined aliases
    if clean_target in KNOWN_APP_MAP:
        return KNOWN_APP_MAP[clean_target], 1.0, clean_target

    # 2. Substring matching in predefined aliases
    for alias, cmd in KNOWN_APP_MAP.items():
        if alias in clean_target or clean_target in alias:
            return cmd, 0.9, alias

    # 3. Scan Registry App Paths
    registry_apps = scan_windows_app_paths()
    if clean_target in registry_apps:
        return registry_apps[clean_target], 1.0, clean_target

    # 4. Fuzzy matching across known aliases and registry
    all_candidates = list(KNOWN_APP_MAP.keys()) + list(registry_apps.keys())
    close_matches = difflib.get_close_matches(clean_target, all_candidates, n=1, cutoff=0.55)
    
    if close_matches:
        best_match = close_matches[0]
        matcher = difflib.SequenceMatcher(None, clean_target, best_match)
        score = matcher.ratio()
        
        if best_match in KNOWN_APP_MAP:
            return KNOWN_APP_MAP[best_match], score, best_match
        elif best_match in registry_apps:
            return registry_apps[best_match], score, best_match

    # 5. Default fallback to raw target command
    return clean_target, 0.4, clean_target

def launch_application(app_name: str) -> Dict[str, Any]:
    """
    Launches a native application on Windows.
    Returns structured execution result.
    """
    resolved_cmd, confidence, matched_name = resolve_application(app_name)
    
    if not resolved_cmd:
        return {
            "success": False,
            "target": app_name,
            "matched_name": None,
            "command": None,
            "error": f"Could not find application '{app_name}'."
        }

    try:
        # Launch non-blocking subprocess
        if resolved_cmd.startswith("start "):
            subprocess.Popen(resolved_cmd, shell=True)
        else:
            # Handle quoted paths or direct executable
            if os.path.exists(resolved_cmd):
                subprocess.Popen([resolved_cmd], shell=True)
            else:
                subprocess.Popen(f"start {resolved_cmd}", shell=True)
                
        return {
            "success": True,
            "target": app_name,
            "matched_name": matched_name,
            "command": resolved_cmd,
            "confidence": round(confidence, 2),
            "output": f"Successfully launched {matched_name.capitalize()}."
        }
    except Exception as e:
        return {
            "success": False,
            "target": app_name,
            "matched_name": matched_name,
            "command": resolved_cmd,
            "error": f"Failed to launch '{app_name}': {str(e)}"
        }

def close_application(app_name: str) -> Dict[str, Any]:
    """
    Finds and terminates running processes matching the given application name.
    """
    clean_target = app_name.strip().lower()
    terminated_count = 0
    closed_pids = []
    
    # Map common alias to process name
    proc_target = KNOWN_APP_MAP.get(clean_target, clean_target)
    if proc_target.endswith(".exe"):
        proc_target = proc_target.replace(".exe", "")
    if proc_target.startswith("start "):
        proc_target = proc_target.replace("start ", "").strip()

    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            p_name = (proc.info['name'] or '').lower()
            if clean_target in p_name or proc_target in p_name:
                proc.terminate()
                closed_pids.append(proc.info['pid'])
                terminated_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if terminated_count > 0:
        return {
            "success": True,
            "target": app_name,
            "terminated_count": terminated_count,
            "pids": closed_pids,
            "output": f"Successfully closed {terminated_count} instance(s) of '{app_name}'."
        }
    else:
        return {
            "success": False,
            "target": app_name,
            "terminated_count": 0,
            "error": f"No active process found for '{app_name}'."
        }


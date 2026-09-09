import os
import re
import sys
import time
import json
import urllib.parse
import webbrowser
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from app.core.telemetry import get_system_telemetry

WORKSPACE_DIR = Path(__file__).parent.parent.parent
NOTES_FILE = WORKSPACE_DIR / "agent_notes.txt"

APP_MAP = {
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "vs code": "code",
    "vscode": "code",
    "code": "code",
    "browser": "start https://www.google.com",
    "chrome": "start chrome",
    "edge": "start msedge",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "terminal": "start wt.exe || start powershell.exe",
    "cmd": "start cmd.exe",
    "powershell": "start powershell.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "spotify": "start spotify:",
    "settings": "start ms-settings:",
    "windows settings": "start ms-settings:",
    "paint": "mspaint.exe",
    "control panel": "control.exe",
}

def execute_shell_command(command: str, timeout: int = 15) -> Dict[str, Any]:
    """Executes a shell command on Windows and returns detailed execution info."""
    start_time = time.time()
    try:
        # Use PowerShell or cmd
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE_DIR)
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "command": command,
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "execution_time_ms": elapsed_ms,
            "timestamp": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "command": command,
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds.",
            "execution_time_ms": elapsed_ms,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "command": command,
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": str(e),
            "execution_time_ms": elapsed_ms,
            "timestamp": datetime.now().isoformat()
        }

def launch_app(app_name: str) -> Dict[str, Any]:
    """Launches an application by name or path."""
    app_key = app_name.strip().lower()
    command = APP_MAP.get(app_key, app_name)
    try:
        subprocess.Popen(command, shell=True)
        return {
            "action": f"Launch {app_name}",
            "command": command,
            "success": True,
            "output": f"Successfully launched {app_name}."
        }
    except Exception as e:
        return {
            "action": f"Launch {app_name}",
            "command": command,
            "success": False,
            "output": f"Failed to launch {app_name}: {e}"
        }

def open_web_search(query: str, engine: str = "google") -> Dict[str, Any]:
    """Opens a web search query in the user's default browser."""
    clean_query = query.strip()
    encoded = urllib.parse.quote_plus(clean_query)
    if engine.lower() == "duckduckgo":
        url = f"https://duckduckgo.com/?q={encoded}"
    else:
        url = f"https://www.google.com/search?q={encoded}"
        
    try:
        webbrowser.open(url)
        return {
            "action": f"Web Search: {clean_query}",
            "url": url,
            "success": True,
            "output": f"Opened search for '{clean_query}' in your browser."
        }
    except Exception as e:
        return {
            "action": f"Web Search: {clean_query}",
            "url": url,
            "success": False,
            "output": f"Failed to open browser search: {e}"
        }

def open_url_in_browser(url: str) -> Dict[str, Any]:
    """Opens a specific URL in the browser."""
    target_url = url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = "https://" + target_url
    try:
        webbrowser.open(target_url)
        return {
            "action": f"Open URL: {target_url}",
            "url": target_url,
            "success": True,
            "output": f"Navigated to {target_url}."
        }
    except Exception as e:
        return {
            "action": f"Open URL: {target_url}",
            "url": target_url,
            "success": False,
            "output": f"Failed to open URL: {e}"
        }

def get_system_summary() -> Dict[str, Any]:
    """Gets human-readable system summary for the assistant."""
    telemetry = get_system_telemetry()
    cpu_percent = telemetry["cpu"]["percent"]
    mem_used = telemetry["memory"]["used_gb"]
    mem_total = telemetry["memory"]["total_gb"]
    mem_percent = telemetry["memory"]["percent"]
    disk_free = telemetry["disk"]["free_gb"]
    disk_total = telemetry["disk"]["total_gb"]
    uptime = telemetry["uptime"]["formatted"]
    os_name = f"{telemetry['os']['system']} {telemetry['os']['release']}"
    
    battery_text = ""
    if telemetry.get("battery"):
        b = telemetry["battery"]
        charging = "charging" if b["power_plugged"] else "on battery"
        battery_text = f", Battery: {b['percent']}% ({charging})"
        
    summary = (
        f"OS: {os_name} | CPU: {cpu_percent}% ({telemetry['cpu']['cores']} cores) | "
        f"RAM: {mem_used} GB / {mem_total} GB ({mem_percent}%) | "
        f"Disk: {disk_free} GB free of {disk_total} GB | "
        f"Uptime: {uptime}{battery_text}"
    )
    return {
        "action": "System Diagnostics",
        "telemetry": telemetry,
        "summary": summary,
        "success": True,
        "output": summary
    }

def take_note(note_text: str) -> Dict[str, Any]:
    """Appends a timestamped note to agent_notes.txt."""
    clean_note = note_text.strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_entry = f"[{timestamp}] {clean_note}\n"
    try:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_entry)
        return {
            "action": "Take Note",
            "file": str(NOTES_FILE),
            "success": True,
            "output": f"Note saved successfully: '{clean_note}'"
        }
    except Exception as e:
        return {
            "action": "Take Note",
            "file": str(NOTES_FILE),
            "success": False,
            "output": f"Failed to save note: {e}"
        }

def list_workspace_files() -> Dict[str, Any]:
    """Lists files in the project workspace."""
    try:
        files = []
        for item in WORKSPACE_DIR.iterdir():
            if item.name.startswith("."):
                continue
            item_type = "Directory" if item.is_dir() else "File"
            size_kb = round(item.stat().st_size / 1024, 1) if item.is_file() else "-"
            files.append({"name": item.name, "type": item_type, "size_kb": size_kb})
        return {
            "action": "List Workspace Files",
            "files": files,
            "success": True,
            "output": f"Found {len(files)} items in workspace directory."
        }
    except Exception as e:
        return {
            "action": "List Workspace Files",
            "files": [],
            "success": False,
            "output": f"Failed to list files: {e}"
        }

def get_current_date_time() -> Dict[str, Any]:
    """Returns formatted current date, time, and timezone information."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M:%S %p")
    return {
        "action": "Current Date & Time",
        "date": date_str,
        "time": time_str,
        "success": True,
        "output": f"It is currently {time_str} on {date_str}."
    }

def lock_computer() -> Dict[str, Any]:
    """Locks the Windows workstation."""
    try:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return {
            "action": "Lock Workstation",
            "success": True,
            "output": "Windows workstation locked."
        }
    except Exception as e:
        return {
            "action": "Lock Workstation",
            "success": False,
            "output": f"Failed to lock workstation: {e}"
        }

def parse_and_execute_actions(response_text: str, auto_execute: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Finds [ACTION: command] tags, executes them if auto_execute is True,
    records execution details, and returns cleaned speech text and list of actions.
    """
    action_pattern = r"\[ACTION:\s*(.+?)\]"
    actions_found = re.findall(action_pattern, response_text)
    executed_actions = []

    for action_cmd in actions_found:
        action_cmd = action_cmd.strip()
        if not auto_execute:
            executed_actions.append({
                "command": action_cmd,
                "status": "pending_approval",
                "output": "Waiting for user confirmation to execute.",
                "execution_time_ms": 0,
                "timestamp": datetime.now().isoformat()
            })
            continue

        # Check if it matches a known application launcher
        app_match = None
        cmd_lower = action_cmd.lower()
        if cmd_lower.startswith("open ") or cmd_lower.startswith("launch "):
            app_target = re.sub(r"^(open|launch)\s+", "", cmd_lower).strip()
            if app_target in APP_MAP:
                res = launch_app(app_target)
                executed_actions.append({
                    "command": action_cmd,
                    "action_type": "app_launch",
                    "status": "success" if res["success"] else "error",
                    "output": res["output"],
                    "execution_time_ms": 50,
                    "timestamp": datetime.now().isoformat()
                })
                continue
                
        # Check if search action
        if cmd_lower.startswith("search ") or cmd_lower.startswith("google "):
            query = re.sub(r"^(search|google)\s+(for\s+)?", "", action_cmd, flags=re.IGNORECASE).strip()
            res = open_web_search(query)
            executed_actions.append({
                "command": action_cmd,
                "action_type": "web_search",
                "status": "success" if res["success"] else "error",
                "output": res["output"],
                "execution_time_ms": 80,
                "timestamp": datetime.now().isoformat()
            })
            continue

        # Otherwise execute as shell command
        print(f"[⚙️] Executing System Action: {action_cmd}")
        exec_res = execute_shell_command(action_cmd)
        executed_actions.append({
            "command": action_cmd,
            "action_type": "shell",
            "status": "success" if exec_res["success"] else "error",
            "return_code": exec_res.get("return_code", 0),
            "stdout": exec_res.get("stdout", ""),
            "stderr": exec_res.get("stderr", ""),
            "output": exec_res.get("stdout", "") or exec_res.get("stderr", "") or "Command executed successfully.",
            "execution_time_ms": exec_res.get("execution_time_ms", 0),
            "timestamp": exec_res.get("timestamp", datetime.now().isoformat())
        })

    # Clean the [ACTION: ...] tags from the text to be spoken
    clean_text = re.sub(action_pattern, "", response_text).strip()
    return clean_text, executed_actions

def match_rule_based_intent(prompt: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
    """
    Intelligent rule-based intent matcher. Used as a high-speed local engine
    or fallback when Ollama is offline.
    """
    p = prompt.strip().lower()
    
    # 1. Open / Launch Apps
    for app_name, command in APP_MAP.items():
        if f"open {app_name}" in p or f"launch {app_name}" in p or f"start {app_name}" in p or p == app_name:
            res = launch_app(app_name)
            spoken = f"Opening {app_name.capitalize()} for you."
            action_item = {
                "command": f"open {app_name}",
                "action_type": "app_launch",
                "status": "success" if res["success"] else "error",
                "output": res["output"],
                "execution_time_ms": 30,
                "timestamp": datetime.now().isoformat()
            }
            return spoken, [action_item]

    # 2. System Diagnostics / Telemetry
    if any(k in p for k in ["system info", "system status", "telemetry", "specs", "cpu usage", "ram usage", "memory usage", "battery status", "diagnostics", "health check"]):
        summary_res = get_system_summary()
        spoken = f"Here is your system telemetry: {summary_res['summary']}"
        action_item = {
            "command": "get_system_telemetry",
            "action_type": "diagnostics",
            "status": "success",
            "output": summary_res["summary"],
            "telemetry": summary_res["telemetry"],
            "execution_time_ms": 25,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 3. Web Search
    search_match = re.search(r"^(search|google|lookup|look up)\s+(for\s+)?(.+)", p)
    if search_match:
        query = search_match.group(3).strip()
        res = open_web_search(query)
        spoken = f"I've opened a web search for '{query}' in your browser."
        action_item = {
            "command": f"search {query}",
            "action_type": "web_search",
            "status": "success",
            "output": res["output"],
            "url": res.get("url"),
            "execution_time_ms": 50,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 4. Open Website / URL
    url_match = re.search(r"^(open|visit|navigate to|go to)\s+(https?://\S+|www\.\S+|\S+\.(com|org|net|io|dev|edu|gov))", p)
    if url_match:
        target_url = url_match.group(2).strip()
        res = open_url_in_browser(target_url)
        spoken = f"Navigating to {target_url}."
        action_item = {
            "command": f"open {target_url}",
            "action_type": "url_open",
            "status": "success",
            "output": res["output"],
            "execution_time_ms": 40,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 5. Date & Time
    if any(k in p for k in ["what time is it", "current time", "what date is it", "what's the date", "today's date", "what day is it", "clock"]):
        dt_res = get_current_date_time()
        spoken = dt_res["output"]
        action_item = {
            "command": "get_date_time",
            "action_type": "clock",
            "status": "success",
            "output": dt_res["output"],
            "execution_time_ms": 5,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 6. Take Note
    note_match = re.search(r"^(take a note|note down|save note|write down|record note)\s*:\s*(.+)", p)
    if not note_match:
        note_match = re.search(r"^(take a note|note down|save note|write down|record note)\s+(.+)", p)
    if note_match:
        note_text = note_match.group(2).strip()
        res = take_note(note_text)
        spoken = f"I've saved that note to your agent notes file."
        action_item = {
            "command": f"note: {note_text}",
            "action_type": "file_note",
            "status": "success" if res["success"] else "error",
            "output": res["output"],
            "execution_time_ms": 15,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 7. List Workspace Files
    if any(k in p for k in ["list files", "show files", "workspace files", "directory files", "what files are here"]):
        files_res = list_workspace_files()
        file_names = [f["name"] for f in files_res.get("files", [])]
        spoken = f"The workspace contains {len(file_names)} items: {', '.join(file_names[:8])}."
        action_item = {
            "command": "list_files",
            "action_type": "file_list",
            "status": "success",
            "output": f"Files: {', '.join(file_names)}",
            "files": files_res.get("files", []),
            "execution_time_ms": 20,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # 8. Lock Workstation
    if any(k in p for k in ["lock screen", "lock computer", "lock my pc", "lock workstation"]):
        lock_res = lock_computer()
        spoken = "Locking your computer now."
        action_item = {
            "command": "lock_screen",
            "action_type": "system_control",
            "status": "success" if lock_res["success"] else "error",
            "output": lock_res["output"],
            "execution_time_ms": 30,
            "timestamp": datetime.now().isoformat()
        }
        return spoken, [action_item]

    # No rule matched
    return None


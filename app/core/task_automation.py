"""
Task Automation & System Control Module
Provides desktop automation, screen locking, process termination, hardware telemetry, and shell execution.
"""

import os
import sys
import ctypes
import webbrowser
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import psutil
from app.core.app_launcher import launch_application, close_application

WORKSPACE_DIR = Path(__file__).parent.parent.parent
NOTES_FILE = WORKSPACE_DIR / "agent_notes.txt"

def lock_workstation() -> Dict[str, Any]:
    """Locks the Windows workstation immediately using user32.dll."""
    try:
        if sys.platform == "win32":
            user32 = ctypes.windll.User32
            result = user32.LockWorkStation()
            if result != 0:
                return {
                    "action": "lock_screen",
                    "success": True,
                    "output": "Windows screen has been locked."
                }
            else:
                # Fallback to rundll32
                subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
                return {
                    "action": "lock_screen",
                    "success": True,
                    "output": "Windows workstation locked via rundll32."
                }
        else:
            return {
                "action": "lock_screen",
                "success": False,
                "error": "Screen locking only supported on Windows in this build."
            }
    except Exception as e:
        return {
            "action": "lock_screen",
            "success": False,
            "error": f"Failed to lock screen: {str(e)}"
        }

def get_detailed_telemetry() -> Dict[str, Any]:
    """
    Collects detailed hardware telemetry (CPU, RAM, GPU presence, Disks, Network, Battery, Uptime).
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores_logical = psutil.cpu_count(logical=True)
    cpu_cores_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()
    
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # GPU detection (NVIDIA via nvidia-smi if installed)
    gpu_info = None
    try:
        smi_out = subprocess.run(
            "nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits",
            shell=True, capture_output=True, text=True, timeout=2
        )
        if smi_out.returncode == 0 and smi_out.stdout.strip():
            parts = [p.strip() for p in smi_out.stdout.strip().split(',')]
            if len(parts) >= 4:
                gpu_info = {
                    "name": parts[0],
                    "memory_total_mb": int(parts[1]),
                    "memory_used_mb": int(parts[2]),
                    "utilization_percent": int(parts[3])
                }
    except Exception:
        gpu_info = None

    # Battery
    battery = psutil.sensors_battery()
    battery_info = None
    if battery:
        battery_info = {
            "percent": round(battery.percent, 1),
            "charging": battery.power_plugged,
            "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1
        }
        
    # Network I/O
    net_io = psutil.net_io_counters()
    
    # Uptime
    uptime_seconds = int(time.time() - psutil.boot_time())
    uptime_hours = uptime_seconds // 3600
    uptime_mins = (uptime_seconds % 3600) // 60
    
    summary_text = (
        f"CPU: {cpu_percent}% ({cpu_cores_logical} cores) | "
        f"RAM: {round(mem.used/(1024**3), 1)}GB / {round(mem.total/(1024**3), 1)}GB ({mem.percent}%) | "
        f"Disk: {round(disk.free/(1024**3), 1)}GB Free | "
        f"Uptime: {uptime_hours}h {uptime_mins}m"
    )
    if gpu_info:
        summary_text += f" | GPU: {gpu_info['name']} ({gpu_info['utilization_percent']}%)"
        
    return {
        "action": "system_telemetry",
        "success": True,
        "summary": summary_text,
        "output": summary_text,
        "cpu": {
            "percent": cpu_percent,
            "cores_logical": cpu_cores_logical,
            "cores_physical": cpu_cores_physical,
            "frequency_mhz": round(cpu_freq.current, 1) if cpu_freq else 0
        },
        "memory": {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "free_gb": round(mem.available / (1024**3), 2),
            "percent": mem.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        },
        "gpu": gpu_info,
        "battery": battery_info,
        "network": {
            "sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "recv_mb": round(net_io.bytes_recv / (1024**2), 2)
        },
        "uptime": {
            "formatted": f"{uptime_hours}h {uptime_mins}m",
            "seconds": uptime_seconds
        }
    }

def execute_web_search(query: str) -> Dict[str, Any]:
    """Opens browser search query."""
    clean_q = query.strip()
    encoded = urllib.parse.quote_plus(clean_q)
    url = f"https://www.google.com/search?q={encoded}"
    try:
        webbrowser.open(url)
        return {
            "action": "web_search",
            "query": clean_q,
            "url": url,
            "success": True,
            "output": f"Opened Google search for '{clean_q}'."
        }
    except Exception as e:
        return {
            "action": "web_search",
            "query": clean_q,
            "success": False,
            "error": f"Failed to open web search: {e}"
        }

def execute_open_url(url: str) -> Dict[str, Any]:
    """Navigates to URL in browser."""
    target = url.strip()
    if not target.startswith("http://") and not target.startswith("https://"):
        target = "https://" + target
    try:
        webbrowser.open(target)
        return {
            "action": "open_url",
            "url": target,
            "success": True,
            "output": f"Opened {target} in browser."
        }
    except Exception as e:
        return {
            "action": "open_url",
            "url": target,
            "success": False,
            "error": f"Failed to navigate to URL: {e}"
        }

def execute_shell_task(command: str, timeout: int = 15) -> Dict[str, Any]:
    """Executes a custom shell / PowerShell task."""
    start_time = time.time()
    try:
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE_DIR)
        )
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "action": "shell_command",
            "command": command,
            "return_code": res.returncode,
            "success": res.returncode == 0,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "output": res.stdout.strip() or res.stderr.strip() or "Command completed successfully.",
            "execution_time_ms": elapsed_ms
        }
    except subprocess.TimeoutExpired:
        return {
            "action": "shell_command",
            "command": command,
            "return_code": -1,
            "success": False,
            "output": f"Execution timed out after {timeout} seconds.",
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }
    except Exception as e:
        return {
            "action": "shell_command",
            "command": command,
            "return_code": -1,
            "success": False,
            "output": str(e),
            "execution_time_ms": int((time.time() - start_time) * 1000)
        }


"""
Windows Control Subsystem
Native automation for windows, keyboard/mouse input, clipboard, volume,
brightness, network adapter status and battery/CPU/RAM monitoring.

Implementation note: input simulation uses Win32 SendInput via ctypes (no
third-party dependency), window manipulation uses user32 (FindWindow/ShowWindow)
and PowerShell AppActivate, and telemetry uses psutil + WMI. Arbitrary shell
commands are avoided in favor of the appropriate Windows API where one exists.
"""

import os
import ctypes
import subprocess
import time
from typing import Dict, Any, List, Optional

import psutil

# ==========================================================
# WINDOW MANAGEMENT
# ==========================================================
user32 = ctypes.windll.user32

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
SW_HIDE = 0
SW_SHOW = 5

GWL_STYLE = -16
WS_MINIMIZEBOX = 0x20000


def _find_window(title_part: str) -> Optional[int]:
    """Returns the first top-level visible window handle whose title contains title_part."""
    result = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))

    def callback(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_part.lower() in buf.value.lower():
                result.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return result[0] if result else None


def _show_window(title_part: str, mode: int) -> Dict[str, Any]:
    hwnd = _find_window(title_part)
    if not hwnd:
        return {"success": False, "error": f"No visible window found matching '{title_part}'."}
    user32.ShowWindow(hwnd, mode)
    user32.SetForegroundWindow(hwnd)
    return {"success": True, "hwnd": int(hwnd), "title": title_part}


def foreground_window() -> Dict[str, Any]:
    """Returns the currently focused window title and process id."""
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"success": True, "title": buf.value, "pid": int(pid.value), "hwnd": int(hwnd)}


def minimize_window(title: str = None) -> Dict[str, Any]:
    """Minimizes a window (default: the foreground window)."""
    if title:
        return _show_window(title, SW_MINIMIZE)
    user32.ShowWindow(user32.GetForegroundWindow(), SW_MINIMIZE)
    return {"success": True, "output": "Minimized the active window."}


def maximize_window(title: str = None) -> Dict[str, Any]:
    """Maximizes a window (default: the foreground window)."""
    if title:
        return _show_window(title, SW_MAXIMIZE)
    user32.ShowWindow(user32.GetForegroundWindow(), SW_MAXIMIZE)
    return {"success": True, "output": "Maximized the active window."}


def restore_window(title: str = None) -> Dict[str, Any]:
    if title:
        return _show_window(title, SW_RESTORE)
    user32.ShowWindow(user32.GetForegroundWindow(), SW_RESTORE)
    return {"success": True, "output": "Restored the active window."}


def switch_windows(title: str) -> Dict[str, Any]:
    """Brings a window to the foreground (Alt-Tab style switching)."""
    res = _show_window(title, SW_RESTORE)
    return {**res, "output": f"Switched to window '{title}'."} if res.get("success") else res


def list_windows(max_windows: int = 30) -> Dict[str, Any]:
    """Lists open visible window titles."""
    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))

    def callback(hwnd, lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            windows.append(buf.value)
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    windows = windows[:max_windows]
    return {"success": True, "windows": windows, "count": len(windows), "output": f"Found {len(windows)} open window(s)."}


# ==========================================================
# SCREENSHOT
# ==========================================================
def take_screenshot(destination: str = None) -> Dict[str, Any]:
    """Captures the primary screen to a PNG file using PIL ImageGrab."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return {"success": False, "error": "pillow is not installed. Run: pip install pillow"}
    try:
        if not destination:
            shot_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "screenshots")
            os.makedirs(shot_dir, exist_ok=True)
            destination = os.path.join(shot_dir, f"screen_{int(time.time())}.png")
        img = ImageGrab.grab()
        img.save(destination)
        return {"success": True, "path": destination, "output": f"Screenshot saved to {destination}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================================
# KEYBOARD / MOUSE (Win32 SendInput)
# ==========================================================
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_MOVE = 0x0001

_VK_TABLE = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "space": 0x20, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "shift": 0x10, "ctrl": 0x11, "control": 0x11,
    "alt": 0x12, "win": 0x5B, "capslock": 0x14, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75, "f7": 0x76,
    "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "playpause": 0xB3, "next": 0xB0, "prev": 0xB1, "previous": 0xB1,
    "stop": 0xB2, "mute": 0xAD, "volumedown": 0xAE, "volumeup": 0xAF,
}


def _send_input_key(vk: int, key_up: bool = False) -> None:
    """Sends a keyboard event for a scan-based virtual key via SendInput."""
    flags = KEYEVENTF_KEYUP if key_up else 0
    class KEYBDINPUT_S(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_ulonglong)]
    class INPUT_I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT_S)]
    class INPUT_S(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("i", INPUT_I)]
    inp = INPUT_S()
    inp.type = INPUT_KEYBOARD
    inp.i.ki.wVk = vk
    inp.i.ki.wScan = 0
    inp.i.ki.dwFlags = flags
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT_S))


def _send_unicode_char(char: str) -> None:
    class KEYBDINPUT_S(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_ulonglong)]
    class INPUT_I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT_S)]
    class INPUT_S(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("i", INPUT_I)]
    for down in (0, 1):
        inp = INPUT_S()
        inp.type = INPUT_KEYBOARD
        inp.i.ki.wScan = ord(char)
        inp.i.ki.dwFlags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if down else 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT_S))


def type_text(text: str) -> Dict[str, Any]:
    """Types plain text (including letters/numbers) into the focused window."""
    if not text:
        return {"success": False, "error": "No text to type."}
    try:
        for char in text:
            _send_unicode_char(char)
            time.sleep(0.005)
        return {"success": True, "text": text, "output": f"Typed '{text}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_key(key: str) -> Dict[str, Any]:
    """Presses a single key or printable character."""
    vk = _VK_TABLE.get(key.strip().lower())
    if vk is not None:
        _send_input_key(vk)
        _send_input_key(vk, key_up=True)
    else:
        _send_unicode_char(key[0])
    return {"success": True, "key": key, "output": f"Pressed '{key}'."}


def hotkey(*keys: str) -> Dict[str, Any]:
    """Presses a chord of keys, e.g. hotkey('ctrl', 'c')."""
    try:
        for k in keys:
            vk = _VK_TABLE.get(k.lower())
            if vk is not None:
                _send_input_key(vk)
        for k in reversed(keys):
            vk = _VK_TABLE.get(k.lower())
            if vk is not None:
                _send_input_key(vk, key_up=True)
        return {"success": True, "keys": list(keys), "output": f"Pressed {'+'.join(keys)}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_move(x: int, y: int, absolute: bool = True) -> Dict[str, Any]:
    """Moves the cursor to (x, y). In absolute mode uses screen coordinates."""
    try:
        if absolute:
            user32.SetCursorPos(int(x), int(y))
        else:
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetCursorPos(pt.x + int(x), pt.y + int(y))
        return {"success": True, "x": int(x), "y": int(y), "output": f"Cursor moved to ({x}, {y})."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_click(x: int = None, y: int = None, button: str = "left", double: bool = False) -> Dict[str, Any]:
    """Clicks at the given position (or current cursor position)."""
    try:
        if x is not None and y is not None:
            mouse_move(x, y)
        down, up = (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP) if button.lower() in ("left",) else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
        if double:
            for _ in range(2):
                user32.mouse_event(down, 0, 0, 0, 0)
                user32.mouse_event(up, 0, 0, 0, 0)
        else:
            user32.mouse_event(down, 0, 0, 0, 0)
            user32.mouse_event(up, 0, 0, 0, 0)
        return {"success": True, "button": button, "double": double, "output": f"Performed {'double-' if double else ''}{button} click."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_scroll(lines: int = 3) -> Dict[str, Any]:
    """Scrolls the mouse wheel. Positive = up, negative = down."""
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(lines) * 120, 0)
    return {"success": True, "lines": lines, "output": f"Scrolled {'up' if lines > 0 else 'down'} by {abs(lines)} notches."}


# ==========================================================
# CLIPBOARD
# ==========================================================
def clipboard_set(text: str) -> Dict[str, Any]:
    """Copies text to the Windows clipboard via PowerShell Set-Clipboard."""
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                       input=text, capture_output=True, text=True, timeout=10, shell=True)
        return {"success": True, "output": "Text copied to clipboard."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clipboard_get() -> Dict[str, Any]:
    """Reads text from the Windows clipboard."""
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                             capture_output=True, text=True, timeout=10, shell=True)
        return {"success": res.returncode == 0, "text": res.stdout.strip(), "output": "Clipboard read successfully."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================================
# VOLUME
# ==========================================================
def _pycaw_volume():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_volume() -> Dict[str, Any]:
    """Returns the current system volume percentage (0-100)."""
    try:
        volume = _pycaw_volume()
        level = int(round(volume.GetMasterVolumeLevelScalar() * 100))
        return {"success": True, "volume": level, "output": f"System volume is {level}%."}
    except Exception:
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "$null; (New-Object -ComObject WScript.Shell).SendKeys('')"],
                capture_output=True, timeout=5, shell=True)
        except Exception:
            pass
        return {"success": False, "error": "Volume query needs pycaw. Run: pip install pycaw comtypes"}


def set_volume(level: int) -> Dict[str, Any]:
    """Sets system volume to a percentage (0-100)."""
    level = max(0, min(100, int(level)))
    try:
        volume = _pycaw_volume()
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return {"success": True, "volume": level, "output": f"System volume set to {level}%."}
    except Exception:
        return {"success": False, "error": "Volume control needs pycaw. Run: pip install pycaw comtypes"}


def adjust_volume(delta: int) -> Dict[str, Any]:
    """Adjusts system volume by delta (-100..100)."""
    current = get_volume()
    if not current.get("success"):
        return current
    return set_volume(current["volume"] + delta)


# ==========================================================
# BRIGHTNESS (WMI)
# ==========================================================
def _ps_brightness(cmd: str) -> Optional[str]:
    wmi_cmd = (
        "Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods | "
        "Invoke-WmiMethod -Name WmiSetBrightness -ArgumentList 1,$level; "
        "Start-Sleep -Milliseconds 300"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=10, shell=True)
        return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None


def get_brightness() -> Dict[str, Any]:
    """Returns the current monitor brightness percentage."""
    cmd = (
        "$b = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness; "
        "Write-Output $b"
    )
    val = _ps_brightness(cmd)
    if val is None:
        return {"success": False, "error": "Could not read brightness (requires WMI brightness support)."}
    try:
        return {"success": True, "brightness": int(val), "output": f"Brightness is {val}%."}
    except ValueError:
        return {"success": False, "error": f"Unexpected brightness value: {val}"}


def set_brightness(level: int) -> Dict[str, Any]:
    """Sets monitor brightness (0-100)."""
    level = max(0, min(100, int(level)))
    cmd = (
        "$level = {level}; "
        "Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods | "
        "Invoke-WmiMethod -Name WmiSetBrightness -ArgumentList 1,$level > $null"
    ).format(level=level)
    _ps_brightness(cmd)
    return {"success": True, "brightness": level, "output": f"Brightness set to {level}%."}


# ==========================================================
# NETWORK / POWER / MONITORING
# ==========================================================
def _adapter_status(adapter_query: str) -> Dict[str, Any]:
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-NetAdapter | Where-Object {{ $_.InterfaceDescription -match '{adapter_query}' }} | Select-Object -First 1 Status,Name | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10, shell=True)
        if res.returncode != 0 or not res.stdout.strip():
            return {"success": False, "error": "Adapter not found or status unavailable."}
        import json as _json
        return {"success": True, "network": _json.loads(res.stdout)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def wifi_status() -> Dict[str, Any]:
    """Returns the Wi-Fi adapter status and connected SSID."""
    status = _adapter_status("Wi-Fi|WLAN|802.11|Wireless")
    ssid = None
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-NetConnectionProfile | Where-Object {$_.Name}).Name"],
                             capture_output=True, text=True, timeout=10, shell=True)
        ssid = res.stdout.strip() or None
    except Exception:
        pass
    result = status.get("network", {}) if status.get("success") else {}
    return {**status, "ssid": ssid, "output": f"Wi-Fi {'connected to ' + ssid if ssid else 'not connected'}."}


def bluetooth_status() -> Dict[str, Any]:
    """Returns whether Bluetooth is enabled."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$a = Get-PnpDevice -Class Bluetooth -EA SilentlyContinue | Where-Object {$_.Status -eq 'OK'} | Select-Object -First 1; if ($a) { 'enabled' } else { 'disabled' }"],
            capture_output=True, text=True, timeout=10, shell=True)
        state = res.stdout.strip()
        return {"success": True, "enabled": state == "enabled", "output": f"Bluetooth is {state}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def battery_info() -> Dict[str, Any]:
    """Returns battery percentage, charging state and remaining time."""
    battery = psutil.sensors_battery()
    if not battery:
        return {"success": False, "error": "No battery detected (this may be a desktop)."}
    return {
        "success": True,
        "percent": round(battery.percent, 1),
        "plugged": battery.power_plugged,
        "charging": bool(battery.power_plugged),
        "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
        "output": f"Battery at {battery.percent}%, {'charging' if battery.power_plugged else 'on battery'}.",
    }


def monitor_cpu_ram() -> Dict[str, Any]:
    """Returns current CPU %, RAM usage and per-core load."""
    cpu_percent = psutil.cpu_percent(interval=0.4)
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    mem = psutil.virtual_memory()
    return {
        "success": True,
        "cpu_percent": cpu_percent,
        "cpu_per_core": per_core,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024 ** 3), 2),
        "memory_total_gb": round(mem.total / (1024 ** 3), 2),
        "output": f"CPU {cpu_percent}% | RAM {mem.percent}% ({round(mem.used/(1024**3),1)}/{round(mem.total/(1024**3),1)} GB).",
    }
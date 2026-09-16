"""
System Control Module — Windows
Handles volume control, screen lock, restart, and shutdown via Windows APIs.
"""

import os
import subprocess
import ctypes
from typing import Dict, Any

# ==========================================
# VOLUME CONTROL (via pycaw or nircmd or PowerShell)
# ==========================================

def _set_volume_pycaw(level: int) -> bool:
    """Use pycaw (Windows COM) to set system volume. Returns True on success."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # pycaw scalar volume: 0.0 to 1.0
        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)
        return True
    except Exception:
        return False

def _set_volume_powershell(level: int) -> bool:
    """Fallback: use PowerShell nircmd or SoundVolumeView to set volume."""
    try:
        # Uses built-in Windows WMI approach via PowerShell
        script = f"""
$wshShell = New-Object -ComObject WScript.Shell
$volume = {int(level)}
$currentVolume = (Get-AudioDevice -Playback).Volume 2>$null
if ($?) {{
    Set-AudioDevice -PlaybackVolume $volume
}} else {{
    # Pure WMI fallback
    $objVolume = New-Object -ComObject SAPI.SpVoice
}}
"""
        # Simpler: use SoundVolumeView if present
        nircmd_paths = [
            r"C:\nircmd\nircmd.exe",
            r"C:\Windows\nircmd.exe",
            r"C:\tools\nircmd.exe"
        ]
        for path in nircmd_paths:
            if os.path.exists(path):
                result = subprocess.run(
                    [path, "setsysvolume", str(int(level * 655.35))],
                    capture_output=True, timeout=5
                )
                return result.returncode == 0

        # Last resort: PowerShell with undocumented volume key
        ps_cmd = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"$obj.SendKeys([char]174)"  # This won't set exact level, just mute toggle
        )
        return False
    except Exception:
        return False

def set_volume(level: int) -> Dict[str, Any]:
    """
    Set system volume (0–100).
    Tries pycaw first, then PowerShell/nircmd.
    """
    level = max(0, min(100, int(level)))
    if _set_volume_pycaw(level):
        return {"success": True, "level": level, "output": f"Volume set to {level}%, Sir."}
    if _set_volume_powershell(level):
        return {"success": True, "level": level, "output": f"Volume set to {level}%, Sir."}
    return {"success": False, "error": "Volume control library not available. Install pycaw: pip install pycaw"}

def increase_volume(step: int = 10) -> Dict[str, Any]:
    """Increase system volume by step (default 10%)."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        current = volume.GetMasterVolumeLevelScalar()
        new_level = min(1.0, current + step / 100.0)
        volume.SetMasterVolumeLevelScalar(new_level, None)
        level_pct = int(new_level * 100)
        return {"success": True, "level": level_pct, "output": f"Volume increased to {level_pct}%, Sir."}
    except Exception:
        # Fallback: Windows media key simulation
        try:
            VK_VOLUME_UP = 0xAF
            for _ in range(max(1, step // 2)):
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
            return {"success": True, "output": f"Volume increased by {step}%, Sir."}
        except Exception as e:
            return {"success": False, "error": str(e)}

def decrease_volume(step: int = 10) -> Dict[str, Any]:
    """Decrease system volume by step (default 10%)."""
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        current = volume.GetMasterVolumeLevelScalar()
        new_level = max(0.0, current - step / 100.0)
        volume.SetMasterVolumeLevelScalar(new_level, None)
        level_pct = int(new_level * 100)
        return {"success": True, "level": level_pct, "output": f"Volume decreased to {level_pct}%, Sir."}
    except Exception:
        try:
            VK_VOLUME_DOWN = 0xAE
            for _ in range(max(1, step // 2)):
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
            return {"success": True, "output": f"Volume decreased by {step}%, Sir."}
        except Exception as e:
            return {"success": False, "error": str(e)}

def mute_volume() -> Dict[str, Any]:
    """Toggle mute on the system audio."""
    try:
        VK_VOLUME_MUTE = 0xAD
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
        return {"success": True, "output": "Audio muted, Sir."}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==========================================
# POWER MANAGEMENT
# ==========================================

def shutdown_pc(delay_seconds: int = 5) -> Dict[str, Any]:
    """Schedule a system shutdown after delay_seconds."""
    try:
        subprocess.run(
            f"shutdown /s /t {delay_seconds}",
            shell=True, check=True
        )
        return {
            "success": True,
            "output": f"System shutdown initiated. Powering off in {delay_seconds} seconds, Sir."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def restart_pc(delay_seconds: int = 5) -> Dict[str, Any]:
    """Schedule a system restart after delay_seconds."""
    try:
        subprocess.run(
            f"shutdown /r /t {delay_seconds}",
            shell=True, check=True
        )
        return {
            "success": True,
            "output": f"System restart initiated. Rebooting in {delay_seconds} seconds, Founder Prajjwal."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def cancel_shutdown() -> Dict[str, Any]:
    """Cancel a pending shutdown or restart."""
    try:
        subprocess.run("shutdown /a", shell=True, check=True)
        return {"success": True, "output": "Shutdown/restart cancelled, Sir."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sleep_pc() -> Dict[str, Any]:
    """Put the PC to sleep."""
    try:
        subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return {"success": True, "output": "Putting the system to sleep, Sir."}
    except Exception as e:
        return {"success": False, "error": str(e)}

import psutil
import platform
import time
from datetime import datetime
from typing import Dict, Any

_last_net_io = None
_last_net_time = None

def get_system_telemetry() -> Dict[str, Any]:
    """Retrieves real-time system metrics (CPU, RAM, Disk, Network, Battery)."""
    global _last_net_io, _last_net_time
    
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Battery info
    battery = psutil.sensors_battery()
    battery_info = None
    if battery:
        battery_info = {
            "percent": round(battery.percent, 1),
            "power_plugged": battery.power_plugged,
            "secsleft": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1
        }
        
    # Network speed calculation
    net_io = psutil.net_io_counters()
    current_time = time.time()
    download_speed_kb = 0.0
    upload_speed_kb = 0.0
    
    if _last_net_io and _last_net_time:
        time_diff = current_time - _last_net_time
        if time_diff > 0:
            bytes_recv_diff = net_io.bytes_recv - _last_net_io.bytes_recv
            bytes_sent_diff = net_io.bytes_sent - _last_net_io.bytes_sent
            download_speed_kb = round((bytes_recv_diff / 1024) / time_diff, 1)
            upload_speed_kb = round((bytes_sent_diff / 1024) / time_diff, 1)
            
    _last_net_io = net_io
    _last_net_time = current_time
    
    # Boot time / Uptime
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = int(time.time() - psutil.boot_time())
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
            "cores": cpu_count,
            "freq_mhz": round(cpu_freq.current, 1) if cpu_freq else 0
        },
        "memory": {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "free_gb": round(mem.available / (1024**3), 2),
            "percent": mem.percent
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent
        },
        "network": {
            "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
            "download_speed_kb": download_speed_kb,
            "upload_speed_kb": upload_speed_kb
        },
        "battery": battery_info,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        },
        "uptime": {
            "boot_time": boot_time.strftime("%Y-%m-%d %H:%M:%S"),
            "formatted": f"{uptime_hours}h {uptime_minutes}m",
            "seconds": uptime_seconds
        }
    }


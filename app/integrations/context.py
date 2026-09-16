"""
Agent Context Module
Gives the agent situational awareness: where the user is (IP geolocation) and
what work it has been doing (recent conversation + executed actions).
"""

import re
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests

_LOCATION: Optional[Dict[str, Any]] = None


def get_user_location(force: bool = False) -> Dict[str, Any]:
    """Returns the approximate location of the machine (city, region, country)."""
    global _LOCATION
    if _LOCATION and not force:
        return _LOCATION

    entry: Dict[str, Any] = {
        "success": False,
        "hostname": socket.gethostname(),
        "city": None,
        "region": None,
        "country": None,
        "timezone": None,
    }
    try:
        resp = requests.get("http://ip-api.com/json", timeout=(5.0, 8.0))
        if resp.status_code == 200:
            d = resp.json()
            entry.update({
                "success": bool(d.get("status") == "success"),
                "city": d.get("city"),
                "region": d.get("regionName"),
                "country": d.get("country"),
                "country_code": d.get("countryCode"),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
                "timezone": d.get("timezone"),
            })
    except Exception:
        pass
    _LOCATION = entry
    return entry


def location_hint() -> str:
    loc = get_user_location()
    if loc.get("city"):
        parts = [p for p in (loc.get("city"), loc.get("region"), loc.get("country")) if p]
        return ", ".join(parts) + "."
    return "unknown."


def build_context_summary(history: List[Dict[str, str]] = None, last_actions: List[str] = None) -> str:
    """Builds a short context block the LLM can use for situational awareness."""
    now = datetime.now()
    parts = [
        f"Current date and time: {now.strftime('%A, %B %d %Y, %I:%M %p')}.",
        f"User location: {location_hint()}",
        f"Computer hostname: {socket.gethostname()}.",
    ]
    if history:
        recent = history[-4:]
        parts.append("Recent conversation: " + "; ".join(
            f"user said '{m.get('content', '')[:140]}'"
            if m.get("role") == "user"
            else f"you replied '{m.get('content', '')[:140]}'"
            for m in recent
        ) + ".")
    if last_actions:
        parts.append("Tasks you recently executed: " + ", ".join(last_actions[-6:]) + ".")
    return " ".join(parts)


def recent_actions_text(action_entries: List[Dict[str, Any]]) -> List[str]:
    """Converts executed action records into short human strings for context."""
    labels = []
    for act in action_entries or []:
        t = act.get("action_type", "")
        status = act.get("status", "?")
        label = f"{t} ({status})"
        fields = {
            "open_app": ("target", ""),
            "close_app": ("target", ""),
            "web_search": ("query", ""),
            "open_url": ("url", ""),
            "tool": ("app", "capability"),
        }
        keys = fields.get(t, ())
        extra = ""
        if t == "tool":
            extra = f" {act.get('app')}.{act.get('capability')}"
        elif keys:
            k = keys[0]
            v = act.get(k)
            if v:
                extra = f" '{v}'"
            if keys[1] and act.get(keys[1]):
                extra += f" {act.get(keys[1])}"
        labels.append(label + extra)
    return labels
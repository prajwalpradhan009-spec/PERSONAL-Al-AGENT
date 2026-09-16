"""
YouTube Automation Module
Searches and plays YouTube videos, music, and tutorials via the default browser.
"""

import webbrowser
import urllib.parse
import time
from typing import Dict, Any

def play_youtube(query: str) -> Dict[str, Any]:
    """
    Opens YouTube in the default browser and plays / searches the given query.
    Tries pywhatkit first for direct autoplay; falls back to browser search URL.
    """
    if not query or not query.strip():
        return {"success": False, "error": "No search query provided."}

    query = query.strip()
    encoded = urllib.parse.quote(query)

    # Try pywhatkit for autoplay (if installed)
    try:
        import pywhatkit
        now = time.localtime()
        hour = now.tm_hour
        minute = now.tm_min + 1  # play 1 minute from now
        if minute >= 60:
            minute = 0
            hour = (hour + 1) % 24
        pywhatkit.playonyt(query)
        return {
            "success": True,
            "method": "pywhatkit",
            "query": query,
            "output": f"Playing '{query}' on YouTube via pywhatkit."
        }
    except ImportError:
        pass
    except Exception as e:
        pass  # fallback to browser

    # Fallback: open YouTube search URL in browser
    url = f"https://www.youtube.com/results?search_query={encoded}"
    try:
        webbrowser.open(url)
        return {
            "success": True,
            "method": "browser_search",
            "query": query,
            "url": url,
            "output": f"Opened YouTube search for '{query}' in your browser, Sir."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def open_youtube_url(url: str) -> Dict[str, Any]:
    """Opens a specific YouTube URL directly."""
    try:
        webbrowser.open(url)
        return {"success": True, "url": url, "output": f"Opened YouTube URL: {url}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

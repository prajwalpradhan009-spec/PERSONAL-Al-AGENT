"""
Browser Automation Subsystem (Playwright)
Drives Chrome / Edge / Firefox for reliable web automation.

No credentials required. Uses a lazy singleton Playwright-controlled browser so
consecutive commands operate on the same page. If Playwright (or its browser
binary) is unavailable, functions fall back to OS-level webbrowser opening and
return an error for interactive DOM actions with a setup hint.

Browser channel config (config.json -> credentials block):
    browser_channel: "msedge" | "chrome" | "firefox" | ""  ("" -> bundled chromium)

Style-convention note: each capability function takes primitive, serializable
arguments so the agent's structured action dispatcher can call it directly from JSON.
"""

import os
import time
import pathlib
import webbrowser
import urllib.parse
from typing import Dict, Any, List, Optional

from app.core.config import load_config

_BROWSER = None
_PAGE = None
_LAST_ERROR_HINT = (
    "Playwright is not available or its browser is not installed. "
    "Run:  pip install playwright  then  playwright install chromium  (or msedge/chrome)."
)


# ==========================================================
# Browser lifecycle
# ==========================================================
def _base_url() -> str:
    config = load_config()
    return config.get("browser_url", "https://www.google.com")


def _get_browser():
    """Returns the singleton Playwright browser instance."""
    global _BROWSER, _PAGE
    if _BROWSER is not None and _PAGE is not None:
        return _BROWSER, _PAGE
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(_LAST_ERROR_HINT)

    config = load_config()
    creds = config.get("credentials", {})
    channel = creds.get("browser_channel", "") or ""

    pw = sync_playwright().start()
    if channel.lower() in ("msedge", "edge"):
        browser = pw.chromium.launch(channel="msedge", headless=False)
    elif channel.lower() in ("chrome", "google chrome"):
        browser = pw.chromium.launch(channel="chrome", headless=False)
    elif channel.lower() == "firefox":
        browser = pw.firefox.launch(headless=False)
    else:
        browser = pw.chromium.launch(headless=False)
    page = browser.new_page()
    _BROWSER, _PAGE = browser, page
    return browser, page


def close_browser() -> Dict[str, Any]:
    """Shuts down the managed automation browser (if open)."""
    global _BROWSER, _PAGE
    try:
        if _BROWSER is not None:
            _BROWSER.close()
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        _BROWSER = None
        _PAGE = None
    return {"success": True, "output": "Automation browser closed."}


# ==========================================================
# Capabilities
# ==========================================================
def open_browser() -> Dict[str, Any]:
    """Opens the user's default web browser at the configured start URL."""
    url = _base_url()
    try:
        webbrowser.open(url)
        return {"success": True, "url": url, "output": f"Opened the browser at {url}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def open_url(url: str, new_tab: bool = True) -> Dict[str, Any]:
    """
    Opens a URL. Prefers the managed Playwright browser; falls back to the
    OS default browser via webbrowser.
    """
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        _, page = _get_browser()
        page.goto(target, timeout=30000, wait_until="domcontentloaded")
        time.sleep(0.6)
        return {
            "success": True,
            "url": target,
            "title": page.title(),
            "output": f"Navigated to {target}.",
        }
    except RuntimeError as e:
        webbrowser.open(target)
        return {"success": True, "fallback": str(e), "url": target, "output": f"Opened {target} in the default browser."}
    except Exception as e:
        webbrowser.open(target)
        return {"success": True, "url": target, "error": str(e), "output": f"Opened {target} in the default browser."}


def search_web(query: str, engine: str = "google", num_results: int = 5) -> Dict[str, Any]:
    """
    Searches the web and returns the top result links + titles.
    engines: google | bing | duckduckgo
    """
    q = query.strip()
    if not q:
        return {"success": False, "error": "No search query provided."}
    engines = {
        "google": "https://www.google.com/search?q={}",
        "bing": "https://www.bing.com/search?q={}",
        "duckduckgo": "https://duckduckgo.com/?q={}",
    }
    template = engines.get(engine.lower(), engines["google"])
    url = template.format(urllib.parse.quote_plus(q))
    try:
        _, page = _get_browser()
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(1.2)
        results = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(e => ({text: e.innerText.trim(), href: e.href}))
               .filter(r => r.text.length > 8 && r.href.startsWith('http'))
               .slice(0, 20)""",
        )
        dedup = []
        seen = set()
        for r in results:
            if r["href"] in seen:
                continue
            seen.add(r["href"])
            dedup.append(r)
        top = dedup[:num_results]
        return {"success": True, "engine": engine, "url": url, "results": top, "output": f"Found {len(top)} results for '{q}'."}
    except RuntimeError as e:
        webbrowser.open(url)
        return {"success": True, "fallback": str(e), "url": url, "results": [], "output": f"Opened {engine} search for '{q}'."}
    except Exception as e:
        webbrowser.open(url)
        return {"success": True, "url": url, "error": str(e), "results": [], "output": f"Opened {engine} search for '{q}'."}


def find_text(text: str) -> Dict[str, Any]:
    """Searches the current page for visible text and returns matched counts."""
    if not text:
        return {"success": False, "error": "No text provided."}
    try:
        _, page = _get_browser()
        body = page.inner_text("body")
        count = body.lower().count(text.lower())
        return {"success": True, "text": text, "matches": count, "found": count > 0, "output": f"Found {count} match(es) for '{text}'."}
    except Exception as e:
        return {"success": False, "error": f"{e}. Hint: open a page first with 'open_url'."}


def click_element(selector: str) -> Dict[str, Any]:
    """Clicks the first element matching a CSS selector."""
    try:
        _, page = _get_browser()
        page.click(selector, timeout=5000)
        time.sleep(0.4)
        return {"success": True, "selector": selector, "output": f"Clicked element '{selector}'."}
    except Exception as e:
        return {"success": False, "selector": selector, "error": str(e)}


def click_link_by_text(text: str) -> Dict[str, Any]:
    """Clicks a link whose visible text contains the given string."""
    try:
        _, page = _get_browser()
        page.click(f"a:has-text('{text}')", timeout=5000)
        time.sleep(0.4)
        return {"success": True, "text": text, "output": f"Clicked link containing '{text}'."}
    except Exception as e:
        return {"success": False, "text": text, "error": str(e)}


def type_text(selector: str, text: str, submit: bool = False) -> Dict[str, Any]:
    """Types text into an input field, optionally pressing Enter."""
    try:
        _, page = _get_browser()
        page.fill(selector, text, timeout=5000)
        if submit:
            page.press(selector, "Enter")
            time.sleep(0.5)
        return {"success": True, "selector": selector, "output": f"Typed into '{selector}'." + (" and submitted." if submit else "")}
    except Exception as e:
        return {"success": False, "selector": selector, "error": str(e)}


def scroll_page(direction: str = "down", amount: int = 800) -> Dict[str, Any]:
    """Scrolls the current page up/down by a number of pixels or a page length."""
    amount = int(amount)
    delta = amount if direction.lower() in ("down", "below", "bottom") else -amount
    try:
        _, page = _get_browser()
        page.mouse.wheel(0, delta)
        time.sleep(0.3)
        return {"success": True, "direction": direction, "amount": amount, "output": f"Scrolled {direction} by {amount}px."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_webpage_text(url: str = None, max_chars: int = 8000) -> Dict[str, Any]:
    """Extracts visible text from the current (or given) page."""
    try:
        browser, page = _get_browser()
        if url:
            target = url if url.startswith("http") else f"https://{url}"
            page.goto(target, timeout=30000, wait_until="domcontentloaded")
            time.sleep(0.6)
        text = page.inner_text("body")[:max_chars]
        return {"success": True, "url": page.url, "title": page.title(), "text": text, "output": f"Read {len(text)} characters from the page."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def download_file(url: str, destination: str = None) -> Dict[str, Any]:
    """Downloads a file from the current page (or a direct URL) to disk."""
    try:
        browser, page = _get_browser()
        if not destination:
            dest_dir = pathlib.Path.home() / "Downloads"
            dest_dir.mkdir(parents=True, exist_ok=True)
            destination = str(dest_dir / "agent_download.bin")

        dest_path = pathlib.Path(destination)

        if url:
            import requests as rq
            resp = rq.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        else:
            with page.expect_download(timeout=30000) as dl_info:
                # Expect a download to be triggered by user interaction; if none,
                # this raises and we surface a clear message.
                raise RuntimeError("A user action was required to trigger the download; provide a direct URL.")
            download = dl_info.value
            download.save_as(dest_path)

        size = dest_path.stat().st_size if dest_path.exists() else 0
        return {"success": True, "url": url, "destination": str(dest_path), "size_bytes": size, "output": f"Downloaded to {dest_path} ({size} bytes)."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_file(selector: str, file_path: str) -> Dict[str, Any]:
    """Uploads a file through an <input type=file> element."""
    try:
        _, page = _get_browser()
        page.set_input_files(selector, file_path, timeout=5000)
        return {"success": True, "selector": selector, "file": file_path, "output": f"Uploaded '{file_path}'."}
    except Exception as e:
        return {"success": False, "selector": selector, "error": str(e)}


def take_screenshot(destination: str = None) -> Dict[str, Any]:
    """
    Captures a screenshot of the current page.
    Default destination: <workspace>/screenshots/<timestamp>.png
    """
    try:
        _, page = _get_browser()
        if not destination:
            shot_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "screenshots"
            shot_dir.mkdir(parents=True, exist_ok=True)
            destination = str(shot_dir / f"browser_{int(time.time())}.png")
        page.screenshot(path=destination, full_page=False)
        return {"success": True, "path": destination, "output": f"Screenshot saved to {destination}."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def page_state() -> Dict[str, Any]:
    """Reports the current page URL, title and loading state."""
    try:
        _, page = _get_browser()
        return {
            "success": True,
            "url": page.url,
            "title": page.title(),
            "content_length": len(page.content()),
            "output": f"Current page: {page.title()} ({page.url})",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_links(max_links: int = 20) -> Dict[str, Any]:
    """Lists visible links on the current page."""
    try:
        _, page = _get_browser()
        links = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => ({text: e.innerText.trim(), href: e.href})).filter(r => r.href.startsWith('http'))"
        )[:max_links]
        return {"success": True, "links": links, "count": len(links), "output": f"Found {len(links)} links."}
    except Exception as e:
        return {"success": False, "error": str(e)}
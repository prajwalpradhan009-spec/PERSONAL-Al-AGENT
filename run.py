import sys
import os
import time
import webbrowser
import threading
from pathlib import Path

def print_banner():
    banner = r"""
  █████╗ ██╗     ██████╗ ███████╗██████╗  █████╗ ██╗███████╗
 ██╔══██╗██║    ██╔═══██╗██╔════╝██╔══██╗██╔══██╗██║██╔════╝
 ███████║██║    ██║   ██║███████╗██████╔╝███████║██║███████╗
 ██╔══██║██║    ██║   ██║╚════██║██╔═══╝ ██╔══██║██║╚════██║
 ██║  ██║██║    ╚██████╔╝███████║██║     ██║  ██║██║███████║
 ╚═╝  ╚═╝╚═╝     ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝
      🤖 AI VOICE AGENT PLATFORM v2.0 - JARVIS / CYBER HUD
    """
    print(banner)

def open_browser_delayed(url: str, delay: float = 1.5):
    """Opens the web browser after a brief delay for the server to bind."""
    time.sleep(delay)
    print(f"\n[🌐] Launching Animated AI Agent HUD in browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[⚠️] Could not automatically open browser: {e}")

def main():
    print_banner()
    
    # Add project root to sys.path
    root_dir = Path(__file__).parent.resolve()
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
        
    from app.core.config import load_config
    config = load_config()
    
    host = config.get("server_host", "127.0.0.1")
    port = int(config.get("server_port", 8000))
    url = f"http://{host}:{port}"
    
    print(f"[🚀] Starting FastAPI Server on {url}...")
    print(f"[🧠] Partner IP: {config.get('partner_ip')} | Model: {config.get('ollama_model')}")
    print(f"[🗣️] Voice Persona: {config.get('tts_voice')} | Speed: {config.get('tts_speed')}x")
    print(f"[⚡] Live Telemetry, Audio Orb, and Tool Engine Active.\n")
    
    # Launch browser in separate thread
    threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()
    
    import uvicorn
    uvicorn.run("app.server:app", host=host, port=port, log_level="info", reload=False)

if __name__ == "__main__":
    main()


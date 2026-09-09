import os
import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent.parent.parent / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "partner_ip": "192.168.31.48",
    "ollama_port": 11434,
    "ollama_model": "MyCustomAI",
    "tts_voice": "af_heart",
    "tts_speed": 1.0,
    "stt_model_size": "base.en",
    "stt_device": "cpu",
    "auto_execute_actions": True,
    "server_host": "127.0.0.1",
    "server_port": 8000,
    "active_persona": "jarvis",
    "voice_output_enabled": True,
    "theme": "cyberpunk"
}

AVAILABLE_VOICES = [
    {"id": "af_heart", "name": "Heart (Default, Warm Female)", "lang": "en-US"},
    {"id": "af_bella", "name": "Bella (Clear Female)", "lang": "en-US"},
    {"id": "af_nicole", "name": "Nicole (Soft Female)", "lang": "en-US"},
    {"id": "af_sarah", "name": "Sarah (Energetic Female)", "lang": "en-US"},
    {"id": "am_adam", "name": "Adam (Deep Male)", "lang": "en-US"},
    {"id": "am_michael", "name": "Michael (Crisp Male)", "lang": "en-US"},
    {"id": "bf_emma", "name": "Emma (British Female)", "lang": "en-GB"},
    {"id": "bf_isabella", "name": "Isabella (British Soft Female)", "lang": "en-GB"},
    {"id": "bm_george", "name": "George (British Male)", "lang": "en-GB"}
]

PERSONAS = {
    "jarvis": {
        "name": "J.A.R.V.I.S.",
        "description": "Sophisticated, witty, and hyper-capable AI assistant inspired by Tony Stark's AI.",
        "system_prompt": (
            "You are J.A.R.V.I.S., a highly capable, intelligent, and polite AI assistant. "
            "You speak concisely, elegantly, and with subtle wit. "
            "When the user requests an action on their system (e.g. open an application, search the web, "
            "check system diagnostics, or run a command), use the tag [ACTION: <command>] in your response. "
            "Keep verbal explanations crisp, clear, and direct."
        )
    },
    "cyberpunk": {
        "name": "NEO-AI (Cyberpunk)",
        "description": "High-tech cyberpunk neural operator with hacker precision and cyber vibes.",
        "system_prompt": (
            "You are NEO-AI, an advanced cybernetic AI neural operating system. "
            "Your style is sleek, futuristic, and tech-savvy. "
            "When executing system commands, integrate [ACTION: <command>] seamlessly. "
            "Keep responses sharp, actionable, and futuristic."
        )
    },
    "coder": {
        "name": "CodeMaster AI",
        "description": "Senior software engineer, architecture specialist, and coding copilot.",
        "system_prompt": (
            "You are CodeMaster AI, an expert software engineer and technical assistant. "
            "You provide clean, robust code examples with best practices, explain technical concepts clearly, "
            "and assist in system workflows. Use [ACTION: <command>] when launching developer tools or running shell commands."
        )
    },
    "companion": {
        "name": "Aura (Friendly Companion)",
        "description": "Warm, encouraging, and natural conversational partner.",
        "system_prompt": (
            "You are Aura, a friendly, warm, and helpful AI companion. "
            "You converse naturally, show empathy and curiosity, and assist with any daily computer tasks. "
            "Use [ACTION: <command>] for system actions when requested."
        )
    }
}

def load_config() -> Dict[str, Any]:
    """Loads configuration from JSON file, creating it with defaults if missing."""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[⚠️] Error reading config file, using defaults: {e}")
    else:
        save_config(config)
    return config

def save_config(config_data: Dict[str, Any]) -> bool:
    """Saves configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"[❌] Failed to save config: {e}")
        return False


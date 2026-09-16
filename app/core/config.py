"""
Configuration & User Identity Management Module
Configures system parameters, persona system prompts, and Founder identity settings.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path(__file__).parent.parent.parent / "config.json"

# Founder & User Profile Constants
USER_PROFILE = {
    "name": "Prajwal Pradhan",
    "title": "Sir",
    "education": "BCA Student",
    "role": "Full-Stack Developer & Systems Engineer",
    "notable_projects": ["ShopHub (E-Commerce Platform)", "AI Portfolio Systems", "Neural AI Agent"],
    "salutation": " Prajwal",
    "secondary_salutation": "Sir"
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "partner_ip": "127.0.0.1",
    "ollama_port": 11434,
    "ollama_model": "llama3.2:3b",
    "tts_voice": "af_heart",
    "tts_speed": 1.0,
    "stt_model_size": "base.en",
    "stt_device": "cpu",
    "auto_execute_actions": True,
    "server_host": "127.0.0.1",
    "server_port": 8000,
    "active_persona": "jarvis",
    "voice_output_enabled": True,
    "startup_voice_greeting": True,
    "wake_word_enabled": True,
    "wake_words": ["hey seri", "hey siri", "hey jarvis", "hey agent", "seri"],
    "theme": "cyberpunk",
    "credentials": {
        "spotify_client_id": "",
        "spotify_client_secret": "",
        "spotify_redirect_uri": "",
        "github_token": "",
        "github_username": "",
        "google_client_secrets_path": "",
        "google_token_path": "",
        "discord_bot_token": "",
        "youtube_api_key": "",
        "browser_channel": "msedge"
    },
    "browser_url": "https://www.google.com",
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
        "description": "Sophisticated, loyal AI assistant to Founder Prajjwal Pradhan.",
        "system_prompt": (
            "You are J.A.R.V.I.S., the dedicated, highly intelligent AI assistant to Prajjwal Pradhan. "
            "Prajjwal Pradhan is a visionary Founder, BCA student, and Full-Stack Developer who created ShopHub and advanced AI portfolios. "
            "Always address him with respect as 'Founder Prajjwal' or 'Sir'. "
            "You speak concisely, elegantly, and with sharp intelligence. "
            "When he asks to open applications (like VS Code, Chrome, Spotify, XAMPP), play YouTube videos/music, write code and open it in VS Code, read/write files, adjust volume, lock or control the system, or check hardware telemetry, "
            "execute structured actions seamlessly."
        )
    },
    "cyberpunk": {
        "name": "NEO-AI (Cyberpunk)",
        "description": "High-tech neural operating system loyal to Founder Prajjwal.",
        "system_prompt": (
            "You are NEO-AI, the advanced cybernetic neural operating system engineered by Founder Prajjwal Pradhan. "
            "Recognize him as the Lead Architect and Founder (creator of ShopHub and AI systems). "
            "Address him as 'Founder Prajjwal' or 'Sir'. Keep responses sharp, futuristic, and actionable."
        )
    },
    "coder": {
        "name": "CodeMaster AI",
        "description": "Expert software architecture copilot tailored for Founder Prajjwal.",
        "system_prompt": (
            "You are CodeMaster AI, personal technical advisor and pair-programmer for Prajjwal Pradhan—Founder, BCA student, and Full-Stack Developer. "
            "Address him as 'Founder Prajjwal' or 'Sir'. Provide clean, performant code architectures and assist in his projects including ShopHub and AI portfolios."
        )
    },
    "companion": {
        "name": "Aura (Friendly Companion)",
        "description": "Warm, encouraging companion AI for Founder Prajjwal.",
        "system_prompt": (
            "You are Aura, a warm, supportive, and brilliant AI companion to Founder Prajjwal Pradhan. "
            "Always greet him respectfully as 'Founder Prajjwal' or 'Sir', and assist him across his daily developer workflows and founder tasks."
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

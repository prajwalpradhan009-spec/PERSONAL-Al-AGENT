"""
AI Voice Assistant - Standalone CLI Client
Runs voice conversation directly in the terminal with STT, Ollama / Fallback intelligence, Action Execution, and Kokoro TTS.
"""

import os
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import load_config, save_config
from app.core.llm_client import process_agent_turn, check_ollama_status
from app.core.voice_engine import speak_local, listen_and_transcribe_mic

def validate_setup(config: dict) -> bool:
    """Validates Ollama connection and microphone availability."""
    ip = config.get("partner_ip", "192.168.31.48")
    port = config.get("ollama_port", 11434)
    model = config.get("ollama_model", "MyCustomAI")
    
    print(f"[🔍] Checking Ollama Brain connection at {ip}:{port}...")
    status = check_ollama_status(ip, port)
    if status["online"]:
        print(f"[✅] Ollama reachable. Available models: {', '.join(status['models']) or 'None'}")
        if model in status["models"]:
            print(f"[✅] Active Model '{model}' confirmed.")
        else:
            print(f"[⚠️] Model '{model}' not listed. (Will use if available or fallback)")
    else:
        print(f"[ℹ️] Ollama server offline or unreachable. Built-in intelligent offline engine will handle tools & queries.")
        
    return True

def main():
    config = load_config()
    voice = config.get("tts_voice", "af_heart")
    speed = float(config.get("tts_speed", 1.0))
    persona = config.get("active_persona", "jarvis")
    
    print("=====================================================")
    print("🤖 AI Voice Agent CLI Client Online")
    print(f"   Persona: {persona.upper()} | Voice: {voice} ({speed}x)")
    print("   Say 'stop listening' or 'shut down' to exit.")
    print("   Tip: Run 'python run.py' for the Animated Web HUD!")
    print("=====================================================\n")
    
    validate_setup(config)
    
    print("\n[🎙️] Ears and Voice ready. Listening...\n")
    
    while True:
        try:
            user_input = listen_and_transcribe_mic(timeout=10, phrase_time_limit=8)
            
            if not user_input:
                continue
                
            p_lower = user_input.lower()
            if "stop listening" in p_lower or "shut down" in p_lower or "exit assistant" in p_lower:
                farewell = "Shutting down the assistant client interface. Goodbye!"
                print(f"[🗣️] {farewell}")
                speak_local(farewell, voice=voice, speed=speed)
                break
                
            print(f"\n[👤] User: {user_input}")
            print("[🧠] Thinking & Processing...")
            
            result = process_agent_turn(
                prompt=user_input,
                session_id="cli_session",
                persona_id=persona,
                auto_execute=config.get("auto_execute_actions", True)
            )
            
            # Print actions if executed
            if result.get("actions"):
                for act in result["actions"]:
                    print(f"  [⚙️ Action Executed] {act.get('command')} -> {act.get('status')}")
                    if act.get("output"):
                        print(f"    Output: {act['output']}")
                        
            spoken = result.get("spoken_text") or result.get("text")
            print(f"[🤖] Agent: {spoken}\n")
            
            speak_local(spoken, voice=voice, speed=speed)
            
        except KeyboardInterrupt:
            print("\n[🛑] Manual termination requested.")
            break
        except Exception as e:
            print(f"\n[❌] Loop Error: {e}")

if __name__ == "__main__":
    main()
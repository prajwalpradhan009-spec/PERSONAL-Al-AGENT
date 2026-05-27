import os
import re
import json
import requests
import subprocess
import sounddevice as sd
import speech_recognition as sr
from faster_whisper import WhisperModel
from kokoro import KPipeline

# ==========================================
# CONFIGURATION
# ==========================================
# 🛑 INSERT YOUR PARTNER's IP ADDRESS HERE (The Brain)
PARTNER_IP = "192.168.31.48"  
OLLAMA_ENDPOINT = f"http://{PARTNER_IP}:11434/api/generate"
OLLAMA_MODEL = "MyCustomAI" # Matches your custom personality model!

# Initialize STT (Ears)
print("Loading STT Model...")
stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
recognizer = sr.Recognizer()

# Initialize TTS (Voice)
print("Loading TTS Model...")
tts_pipeline = KPipeline(lang_code='a')

def listen_and_transcribe() -> str:
    """The Ears: Records audio from the microphone and transcribes it."""
    with sr.Microphone() as source:
        print("\n[🎙️] Listening...")
        
        recognizer.adjust_for_ambient_noise(source, duration=2) 
        recognizer.dynamic_energy_threshold = True 
        
        try:
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=8)
            print("[🧠] Processing audio...")
            
            # Save audio temporarily so Whisper can read it
            with open("temp_audio.wav", "wb") as f:
                f.write(audio.get_wav_data())
                
            # Transcribe with Whisper
            segments, _ = stt_model.transcribe("temp_audio.wav", beam_size=5)
            text = "".join([segment.text for segment in segments]).strip()
            
            print(f"[🎤] You said: {text}")
            return text
            
        except sr.WaitTimeoutError:
            return "" # Returns empty if no one speaks
        except Exception as e:
            print(f"[❌] Error transcribing: {e}")
            return ""

def send_to_brain(text: str) -> str:
    """The Network: Sends the transcribed text to the Ollama server."""
    print(f"[🌐] Sending to Brain: {text}")
    
    payload = {
        "model": OLLAMA_MODEL, 
        "prompt": text, 
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"[❌] Network Error: {e}")
        return "Sorry, something went wrong communicating with the brain."

def parse_and_execute(response_text: str) -> str:
    """The Hands: Intercepts [ACTION: command] tags, executes them, and cleans the text."""
    action_pattern = r"\[ACTION:\s*(.+?)\]"
    actions = re.findall(action_pattern, response_text)
    
    for action in actions:
        print(f"[⚙️] Executing System Command: {action}")
        try:
            subprocess.Popen(action, shell=True)
        except Exception as e:
            print(f"[❌] Failed to execute {action}: {e}")
            
    clean_spoken_text = re.sub(action_pattern, "", response_text).strip()
    return clean_spoken_text

def speak(text: str):
    """The Voice: Synthesizes and plays the text out loud."""
    if not text:
        return
        
    print(f"[🗣️] Speaking: {text}")
    generator = tts_pipeline(text, voice='af_heart', speed=1.0)
    
    for _, _, audio in generator:
        sd.play(audio, samplerate=24000)
        sd.wait() 

def validate_setup() -> bool:
    """Validates that Ollama is reachable and microphone is available."""
    print("[🔍] Checking Ollama connection...")
    try:
        response = requests.get(f"http://{PARTNER_IP}:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"[✅] Ollama found at {PARTNER_IP}:11434")
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            if OLLAMA_MODEL in model_names:
                print(f"[✅] Model '{OLLAMA_MODEL}' is available")
            else:
                print(f"[⚠️] Model '{OLLAMA_MODEL}' not found. Available: {model_names}")
    except Exception as e:
        print(f"[❌] Ollama not reachable at {OLLAMA_ENDPOINT}")
        return False
    
    print("[🔍] Checking microphone...")
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.1)
        print("[✅] Microphone is ready")
    except Exception as e:
        print(f"[❌] Microphone error: {e}")
        return False
    
    return True

def main():
    print("========================================")
    print("🤖 Local Assistant 'Face & Hands' Online")
    print("========================================")
    
    if not validate_setup():
        print("\n[🛑] Setup validation failed. Please fix the issues above.")
        return
    
    print("\n[🚀] Starting main loop. Say 'stop listening' or 'shut down' to exit.\n")
    
    while True:
        try:
            user_input = listen_and_transcribe()
            
            if not user_input:
                continue
                
            if "stop listening" in user_input.lower() or "shut down" in user_input.lower():
                speak("Shutting down the client interface. Goodbye!")
                break
                
            raw_response = send_to_brain(user_input)
            clean_response = parse_and_execute(raw_response)
            speak(clean_response)
            
        except KeyboardInterrupt:
            print("\n[🛑] Manual termination requested.")
            break
        except Exception as e:
            print(f"\n[❌] Loop Error: {e}")

if __name__ == "__main__":
    main()
"""
Wake Word Detection & Background Activation Module
Listens for activation keywords ('Hey Seri', 'Hey Siri', 'Hey Jarvis', 'Hey Agent', 'Seri') to wake up the assistant.
"""

import re
import time
import threading
from typing import List, Optional, Callable, Tuple
from app.core.config import load_config

DEFAULT_WAKE_WORDS = ["hey seri", "hey siri", "hey jarvis", "hey agent", "seri", "siri", "jarvis"]

def is_wake_word(text: str, custom_wake_words: List[str] = None) -> Tuple[bool, str, str]:
    """
    Checks if transcribed text contains any of the configured wake words.
    Returns (matched: bool, extracted_prompt: str, wake_word_matched: str).
    """
    if not text:
        return False, "", ""
        
    config = load_config()
    wake_words = custom_wake_words or config.get("wake_words", DEFAULT_WAKE_WORDS)
    clean_text = text.strip().lower()

    for ww in wake_words:
        pattern = r"\b" + re.escape(ww) + r"\b"
        match = re.search(pattern, clean_text)
        if match:
            # Extract anything said after the wake word as immediate prompt
            after_text = clean_text[match.end():].strip(" ,:.-")
            return True, after_text, ww
            
    return False, "", ""

class WakeWordDetector:
    """Background listener for wake words on local microphone."""
    def __init__(self, on_wake_callback: Optional[Callable[[str], None]] = None):
        self.on_wake_callback = on_wake_callback
        self.is_running = False
        self.thread = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        print("[👂] Wake Word Engine Online: Listening for 'Hey Seri'...")

    def stop(self):
        self.is_running = False

    def _listen_loop(self):
        from app.core.voice_engine import get_stt_model
        import speech_recognition as sr
        import io
        
        model, recognizer = get_stt_model()
        if not recognizer or not model:
            return

        while self.is_running:
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    try:
                        audio = recognizer.listen(source, timeout=4, phrase_time_limit=4)
                        wav_data = audio.get_wav_data()
                        wav_io = io.BytesIO(wav_data)
                        
                        segments, _ = model.transcribe(wav_io, beam_size=1)
                        transcription = "".join([s.text for s in segments]).strip()
                        
                        matched, prompt_after, matched_word = is_wake_word(transcription)
                        if matched:
                            print(f"\n[⚡ Wake Word Triggered] '{matched_word}' detected in: '{transcription}'")
                            if self.on_wake_callback:
                                self.on_wake_callback(prompt_after)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        time.sleep(0.5)
            except Exception:
                time.sleep(1.0)

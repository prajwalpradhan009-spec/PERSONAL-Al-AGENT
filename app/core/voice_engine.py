import io
import wave
import numpy as np
import threading
from typing import Optional, Dict, Any, Generator

_stt_model = None
_recognizer = None
_tts_pipeline = None
_lock = threading.Lock()

def get_tts_pipeline():
    """Lazy loader for Kokoro TTS pipeline."""
    global _tts_pipeline
    with _lock:
        if _tts_pipeline is None:
            try:
                from kokoro import KPipeline
                print("[⏳] Initializing Kokoro TTS Pipeline...")
                _tts_pipeline = KPipeline(lang_code='a')
                print("[✅] Kokoro TTS Pipeline ready.")
            except Exception as e:
                print(f"[❌] Error loading Kokoro TTS: {e}")
                return None
        return _tts_pipeline

def get_stt_model():
    """Lazy loader for Faster-Whisper STT model."""
    global _stt_model, _recognizer
    with _lock:
        if _stt_model is None:
            try:
                from faster_whisper import WhisperModel
                import speech_recognition as sr
                print("[⏳] Initializing Faster-Whisper STT Model...")
                _stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
                _recognizer = sr.Recognizer()
                print("[✅] Whisper STT Model ready.")
            except Exception as e:
                print(f"[❌] Error loading Whisper STT: {e}")
                return None, None
        return _stt_model, _recognizer

def synthesize_wav_bytes(text: str, voice: str = 'af_heart', speed: float = 1.0) -> Optional[bytes]:
    """
    Synthesizes speech using Kokoro TTS and returns in-memory WAV audio bytes (24000 Hz, 16-bit PCM).
    """
    if not text or not text.strip():
        return None
        
    pipeline = get_tts_pipeline()
    if pipeline is None:
        return None
        
    try:
        generator = pipeline(text.strip(), voice=voice, speed=speed)
        audio_segments = []
        
        for _, _, audio in generator:
            if audio is not None and len(audio) > 0:
                audio_segments.append(audio)
                
        if not audio_segments:
            return None
            
        full_audio = np.concatenate(audio_segments)
        
        # Convert float32 [-1.0, 1.0] to int16 PCM
        audio_int16 = np.clip(full_audio * 32767, -32768, 32767).astype(np.int16)
        
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(1) # Mono
            wf.setsampwidth(2) # 16-bit = 2 bytes
            wf.setframerate(24000) # Kokoro native sample rate
            wf.writeframes(audio_int16.tobytes())
            
        wav_io.seek(0)
        return wav_io.getvalue()
    except Exception as e:
        print(f"[❌] TTS Synthesis error: {e}")
        return None

def speak_local(text: str, voice: str = 'af_heart', speed: float = 1.0) -> bool:
    """Synthesizes text and plays it out loud through local sound device."""
    if not text or not text.strip():
        return False
        
    pipeline = get_tts_pipeline()
    if pipeline is None:
        return False
        
    try:
        import sounddevice as sd
        generator = pipeline(text.strip(), voice=voice, speed=speed)
        for _, _, audio in generator:
            if audio is not None and len(audio) > 0:
                sd.play(audio, samplerate=24000)
                sd.wait()
        return True
    except Exception as e:
        print(f"[❌] Local audio playback error: {e}")
        return False

def listen_and_transcribe_mic(timeout: int = 10, phrase_time_limit: int = 8) -> str:
    """Records audio from local microphone and transcribes it with Whisper."""
    model, recognizer = get_stt_model()
    if model is None or recognizer is None:
        return ""
        
    import speech_recognition as sr
    
    try:
        with sr.Microphone() as source:
            print("[🎙️] Listening for speech...")
            recognizer.adjust_for_ambient_noise(source, duration=0.8)
            recognizer.dynamic_energy_threshold = True
            
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                print("[🧠] Transcribing voice input...")
                
                wav_data = audio.get_wav_data()
                wav_io = io.BytesIO(wav_data)
                
                segments, _ = model.transcribe(wav_io, beam_size=5)
                text = "".join([s.text for s in segments]).strip()
                print(f"[🎤] Transcribed: '{text}'")
                return text
            except sr.WaitTimeoutError:
                return ""
    except Exception as e:
        print(f"[❌] STT Error: {e}")
        return ""

def transcribe_audio_stream(audio_bytes: bytes) -> str:
    """Transcribes raw WAV/Audio bytes received from browser or API."""
    model, _ = get_stt_model()
    if model is None:
        return ""
    try:
        audio_io = io.BytesIO(audio_bytes)
        segments, _ = model.transcribe(audio_io, beam_size=5)
        text = "".join([s.text for s in segments]).strip()
        return text
    except Exception as e:
        print(f"[❌] Stream STT Error: {e}")
        return ""


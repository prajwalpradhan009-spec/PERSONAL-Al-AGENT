"""
Voice Engine Module (Faster-Whisper STT & Kokoro TTS)
Optimized for local low-resource execution and VRAM protection.
"""

import io
import gc
import wave
import numpy as np
import threading
from typing import Optional, Dict, Any

_stt_model = None
_recognizer = None
_tts_pipeline = None
_lock = threading.Lock()

def free_vram():
    """Explicitly frees cached GPU VRAM and performs garbage collection."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass

def get_tts_pipeline():
    """
    Lazy loader for Kokoro TTS pipeline.
    Runs in American English ('a') with float32/int16 memory efficiency.
    """
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

def get_stt_model(device: str = "cpu", compute_type: str = "int8"):
    """
    Lazy loader for Faster-Whisper STT model.
    Runs on CPU with int8 quantization to prevent VRAM competition with Ollama LLMs.
    """
    global _stt_model, _recognizer
    with _lock:
        if _stt_model is None:
            try:
                from faster_whisper import WhisperModel
                import speech_recognition as sr
                print(f"[⏳] Initializing Faster-Whisper ({device}, {compute_type})...")
                _stt_model = WhisperModel(
                    "base.en", 
                    device=device, 
                    compute_type=compute_type,
                    cpu_threads=4
                )
                _recognizer = sr.Recognizer()
                print("[✅] Faster-Whisper STT ready.")
            except Exception as e:
                print(f"[❌] Error loading Faster-Whisper STT: {e}")
                return None, None
        return _stt_model, _recognizer

def synthesize_wav_bytes(text: str, voice: str = 'af_heart', speed: float = 1.0) -> Optional[bytes]:
    """
    Synthesizes speech using Kokoro TTS and returns in-memory 24kHz 16-bit PCM WAV bytes.
    Cleans up VRAM / RAM caches after synthesis.
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
            wf.setframerate(24000) # Kokoro native 24 kHz
            wf.writeframes(audio_int16.tobytes())
            
        wav_io.seek(0)
        result_bytes = wav_io.getvalue()
        
        # Cleanup temporary audio array from RAM/VRAM
        del full_audio
        del audio_int16
        del audio_segments
        free_vram()
        
        return result_bytes
    except Exception as e:
        print(f"[❌] TTS Synthesis error: {e}")
        free_vram()
        return None

def speak_local(text: str, voice: str = 'af_heart', speed: float = 1.0) -> bool:
    """Synthesizes text and plays it directly out loud through local speakers."""
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
        free_vram()
        return True
    except Exception as e:
        print(f"[❌] Local audio playback error: {e}")
        free_vram()
        return False

def listen_and_transcribe_mic(timeout: int = 10, phrase_time_limit: int = 8) -> str:
    """Records audio from microphone and transcribes it with Whisper."""
    model, recognizer = get_stt_model()
    if model is None or recognizer is None:
        return ""
        
    import speech_recognition as sr
    
    try:
        with sr.Microphone() as source:
            print("[🎙️] Listening for speech...")
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            recognizer.dynamic_energy_threshold = True
            
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                print("[🧠] Transcribing with Faster-Whisper...")
                
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
    """Transcribes raw audio bytes received from browser WebSocket or HTTP upload."""
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

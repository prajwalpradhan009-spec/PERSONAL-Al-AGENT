"""
AI Voice Assistant - FastAPI Backend Server & WebSocket Event Bus
Orchestrates Whisper STT, Kokoro TTS, Ollama Function Calling, Native App Launching, and 3D HUD WebSockets.
"""

import os
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import load_config, save_config, AVAILABLE_VOICES, PERSONAS
from app.core.app_launcher import launch_application, close_application
from app.core.task_automation import (
    lock_workstation, 
    get_detailed_telemetry, 
    execute_web_search, 
    execute_open_url, 
    execute_shell_task
)
from app.core.function_calling import process_function_calling_turn, execute_structured_action
from app.core.voice_engine import (
    synthesize_wav_bytes, 
    speak_local, 
    listen_and_transcribe_mic, 
    transcribe_audio_stream,
    free_vram
)

STATIC_DIR = Path(__file__).parent / "static"

# ==========================================
# WEBSOCKET EVENT BUS
# ==========================================
class WebSocketEventBus:
    """Central Event Bus for broadcasting telemetry, agent states, and action execution confirmations."""
    def __init__(self):
        self.active_sockets: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_sockets.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active_sockets.discard(ws)

    async def broadcast(self, payload: Dict[str, Any]):
        for ws in list(self.active_sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                self.active_sockets.discard(ws)

    async def emit_state(self, state: str):
        """Emits agent state transition ('idle', 'listening', 'thinking', 'executing', 'speaking')."""
        await self.broadcast({
            "type": "agent_state",
            "state": state
        })

    async def emit_action_event(self, action_type: str, status: str, details: Dict[str, Any]):
        """Emits structured action execution confirmation."""
        await self.broadcast({
            "type": "action_execution",
            "action": action_type,
            "status": status,
            "details": details
        })

event_bus = WebSocketEventBus()

async def telemetry_stream_worker():
    """Background task streaming live telemetry metrics over WebSocket."""
    while True:
        try:
            if event_bus.active_sockets:
                telemetry = get_detailed_telemetry()
                await event_bus.broadcast({
                    "type": "telemetry",
                    "data": telemetry
                })
        except Exception:
            pass
        await asyncio.sleep(1.5)

def generate_founder_startup_greeting() -> str:
    """
    Generates dynamic voice greeting for Founder Prajjwal Pradhan with real-time telemetry stats.
    """
    try:
        telemetry = get_detailed_telemetry()
        cpu = int(telemetry["cpu"]["percent"])
        ram = int(telemetry["memory"]["percent"])
        gpu = telemetry.get("gpu")
        
        greeting = f"Welcome back, Founder Prajjwal. Core neural HUD is online. CPU is operating at {cpu} percent, with {ram} percent memory utilized."
        if gpu and gpu.get("memory_used_mb"):
            greeting += f" GPU VRAM utilization is at {gpu['memory_used_mb']} megabytes."
        return greeting
    except Exception:
        return "Welcome back, Founder Prajjwal. Core neural HUD is online."

def trigger_startup_voice_greeting():
    """Synthesizes and speaks startup greeting on local speakers using Kokoro TTS."""
    try:
        config = load_config()
        if not config.get("startup_voice_greeting", True):
            return
        voice = config.get("tts_voice", "af_heart")
        speed = float(config.get("tts_speed", 1.0))
        greeting = generate_founder_startup_greeting()
        print(f"\n[🗣️ Startup Greeting] {greeting}\n")
        speak_local(greeting, voice=voice, speed=speed)
    except Exception as e:
        print(f"[⚠️] Startup voice greeting note: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry worker
    telemetry_task = asyncio.create_task(telemetry_stream_worker())
    
    # Startup Voice Greeting for Founder Prajjwal (non-blocking thread)
    asyncio.create_task(asyncio.to_thread(trigger_startup_voice_greeting))
    
    yield
    # Shutdown
    telemetry_task.cancel()
    free_vram()

app = FastAPI(
    title="Autonomous AI Voice Agent Backend",
    version="2.0.0",
    description="Full-stack AI Voice Assistant with Native App Launching & 3D HUD WebSockets",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ChatRequest(BaseModel):
    prompt: str
    session_id: str = "default"
    persona_id: str = "jarvis"
    generate_audio: bool = True
    speak_on_server: bool = False
    auto_execute: bool = True

class AppLaunchRequest(BaseModel):
    app_name: str

class AppCloseRequest(BaseModel):
    app_name: str

class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0

class ConfigUpdateRequest(BaseModel):
    partner_ip: str = None
    ollama_port: int = None
    ollama_model: str = None
    tts_voice: str = None
    tts_speed: float = None
    active_persona: str = None
    auto_execute_actions: bool = None
    voice_output_enabled: bool = None

# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.get("/api/health")
async def health():
    return {"status": "online", "version": "2.0.0", "vram_optimized": True}

@app.get("/api/config")
async def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    config = load_config()
    update_data = req.model_dump(exclude_unset=True)
    config.update(update_data)
    save_config(config)
    await event_bus.broadcast({"type": "config_updated", "config": config})
    return {"status": "success", "config": config}

@app.get("/api/system/stats")
async def get_stats():
    return get_detailed_telemetry()

@app.get("/api/voices")
async def get_voices():
    return {"voices": AVAILABLE_VOICES}

@app.get("/api/personas")
async def get_personas():
    return {"personas": PERSONAS}

# Action Execution Endpoints
@app.post("/api/actions/open_app")
async def api_open_app(req: AppLaunchRequest):
    res = await asyncio.to_thread(launch_application, req.app_name)
    await event_bus.emit_action_event("open_app", "success" if res["success"] else "error", res)
    return res

@app.post("/api/actions/close_app")
async def api_close_app(req: AppCloseRequest):
    res = await asyncio.to_thread(close_application, req.app_name)
    await event_bus.emit_action_event("close_app", "success" if res["success"] else "error", res)
    return res

@app.post("/api/actions/lock_screen")
async def api_lock_screen():
    res = await asyncio.to_thread(lock_workstation)
    await event_bus.emit_action_event("lock_screen", "success" if res["success"] else "error", res)
    return res

@app.post("/api/chat")
async def chat_handler(req: ChatRequest):
    """
    Main LLM processing pipeline:
    1. Whispers/Prompt passed to LLM Function Calling Engine
    2. Forces Ollama structured JSON
    3. Executes native tools (App launching, system controls, diagnostics)
    4. Generates Kokoro speech
    5. Broadcasts confirmations over WebSocket Event Bus
    """
    await event_bus.emit_state("thinking")
    
    # Process turn with structured function calling
    turn_result = await asyncio.to_thread(
        process_function_calling_turn,
        prompt=req.prompt,
        auto_execute=req.auto_execute
    )
    
    # Broadcast action confirmations
    if turn_result.get("actions"):
        await event_bus.emit_state("executing")
        for act in turn_result["actions"]:
            await event_bus.emit_action_event(
                action_type=act.get("action_type", "action"),
                status=act.get("status", "success"),
                details=act
            )
        await asyncio.sleep(0.2)

    # Audio synthesis
    audio_base64 = None
    config = load_config()
    voice = config.get("tts_voice", "af_heart")
    speed = float(config.get("tts_speed", 1.0))
    spoken_text = turn_result.get("spoken_text", "")

    if req.generate_audio and spoken_text:
        await event_bus.emit_state("speaking")
        wav_bytes = await asyncio.to_thread(
            synthesize_wav_bytes,
            text=spoken_text,
            voice=voice,
            speed=speed
        )
        if wav_bytes:
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            
        if req.speak_on_server:
            asyncio.create_task(asyncio.to_thread(
                speak_local,
                text=spoken_text,
                voice=voice,
                speed=speed
            ))

    await event_bus.emit_state("idle")
    
    response_payload = {
        "text": turn_result["text"],
        "spoken_text": spoken_text,
        "json_payload": turn_result.get("json_payload"),
        "actions": turn_result.get("actions", []),
        "source": turn_result.get("source"),
        "timestamp": turn_result.get("timestamp"),
        "audio_base64": audio_base64
    }

    await event_bus.broadcast({
        "type": "new_message",
        "session_id": req.session_id,
        "data": response_payload
    })

    return response_payload

@app.post("/api/voice/listen")
async def voice_listen():
    await event_bus.emit_state("listening")
    text = await asyncio.to_thread(listen_and_transcribe_mic)
    await event_bus.emit_state("idle")
    return {"text": text}

@app.post("/api/voice/tts")
async def voice_tts(req: TTSRequest):
    wav_bytes = await asyncio.to_thread(
        synthesize_wav_bytes,
        text=req.text,
        voice=req.voice,
        speed=req.speed
    )
    if not wav_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis failed.")
    return Response(content=wav_bytes, media_type="audio/wav")

@app.post("/api/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    content = await file.read()
    text = await asyncio.to_thread(transcribe_audio_stream, content)
    return {"text": text}

# ==========================================
# WEBSOCKET EVENT BUS ENDPOINT
# ==========================================
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await event_bus.connect(ws)
    try:
        telemetry = get_detailed_telemetry()
        config = load_config()
        await ws.send_json({
            "type": "init",
            "telemetry": telemetry,
            "config": config,
            "agent_state": "idle"
        })
        
        while True:
            msg = await ws.receive_json()
            m_type = msg.get("type")
            
            if m_type == "ping":
                await ws.send_json({"type": "pong"})
            elif m_type == "execute_command":
                prompt = msg.get("prompt", "")
                if prompt:
                    res = await asyncio.to_thread(process_function_calling_turn, prompt)
                    await ws.send_json({"type": "command_result", "data": res})
            elif m_type == "set_state":
                await event_bus.emit_state(msg.get("state", "idle"))
                
    except WebSocketDisconnect:
        event_bus.disconnect(ws)
    except Exception:
        event_bus.disconnect(ws)

# Serve Static UI
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/")
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "AI Voice Agent Backend Online"}

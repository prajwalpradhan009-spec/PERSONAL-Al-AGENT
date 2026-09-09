import os
import asyncio
import base64
from pathlib import Path
from typing import Dict, Any, List, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import load_config, save_config, AVAILABLE_VOICES, PERSONAS
from app.core.telemetry import get_system_telemetry
from app.core.llm_client import (
    process_agent_turn, 
    check_ollama_status, 
    get_session, 
    list_all_sessions
)
from app.core.tools import (
    execute_shell_command, 
    launch_app, 
    open_web_search, 
    take_note, 
    list_workspace_files, 
    get_system_summary
)
from app.core.voice_engine import (
    synthesize_wav_bytes, 
    speak_local, 
    listen_and_transcribe_mic, 
    transcribe_audio_stream
)

STATIC_DIR = Path(__file__).parent / "static"

# WebSockets Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.discard(connection)

manager = ConnectionManager()

# Background telemetry broadcaster
async def telemetry_worker():
    while True:
        try:
            if manager.active_connections:
                telemetry = get_system_telemetry()
                await manager.broadcast({
                    "type": "telemetry",
                    "data": telemetry
                })
        except Exception as e:
            pass
        await asyncio.sleep(1.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch telemetry broadcaster in background
    task = asyncio.create_task(telemetry_worker())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(
    title="AI Voice Agent HUD", 
    version="2.0.0", 
    description="Futuristic Voice Assistant Platform with Animated HUD & Action Engine",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class ChatRequest(BaseModel):
    prompt: str
    session_id: str = "default"
    persona_id: str = "jarvis"
    generate_audio: bool = True
    speak_on_server: bool = False
    auto_execute: bool = True

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
    theme: str = None

class ActionExecuteRequest(BaseModel):
    command: str

# API Endpoints
@app.get("/api/health")
async def health_check():
    return {"status": "online", "version": "2.0.0"}

@app.get("/api/config")
async def get_config_endpoint():
    config = load_config()
    return config

@app.post("/api/config")
async def update_config_endpoint(req: ConfigUpdateRequest):
    config = load_config()
    update_data = req.model_dump(exclude_unset=True)
    config.update(update_data)
    save_config(config)
    await manager.broadcast({"type": "config_updated", "config": config})
    return {"status": "success", "config": config}

@app.get("/api/voices")
async def get_voices():
    return {"voices": AVAILABLE_VOICES}

@app.get("/api/personas")
async def get_personas():
    return {"personas": PERSONAS}

@app.get("/api/models")
async def get_models():
    config = load_config()
    ip = config.get("partner_ip", "192.168.31.48")
    port = config.get("ollama_port", 11434)
    status = check_ollama_status(ip, port)
    return status

@app.get("/api/system/stats")
async def get_stats():
    return get_system_telemetry()

@app.get("/api/sessions")
async def get_sessions():
    return {"sessions": list_all_sessions()}

@app.get("/api/sessions/{session_id}")
async def get_session_history(session_id: str):
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "messages": session.messages
    }

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # Notify clients agent is thinking
    await manager.broadcast({"type": "agent_state", "state": "thinking"})
    
    # Process turn
    result = await asyncio.to_thread(
        process_agent_turn,
        prompt=req.prompt,
        session_id=req.session_id,
        persona_id=req.persona_id,
        auto_execute=req.auto_execute
    )
    
    # Check if actions were executed
    if result.get("actions"):
        await manager.broadcast({"type": "agent_state", "state": "executing"})
        await asyncio.sleep(0.3)
        
    # Generate TTS audio if requested
    audio_base64 = None
    config = load_config()
    voice = config.get("tts_voice", "af_heart")
    speed = float(config.get("tts_speed", 1.0))
    
    if req.generate_audio and result.get("spoken_text"):
        await manager.broadcast({"type": "agent_state", "state": "speaking"})
        
        # Synthesize WAV bytes
        wav_bytes = await asyncio.to_thread(
            synthesize_wav_bytes,
            text=result["spoken_text"],
            voice=voice,
            speed=speed
        )
        if wav_bytes:
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            
        if req.speak_on_server:
            # Play locally in background thread
            asyncio.create_task(asyncio.to_thread(
                speak_local,
                text=result["spoken_text"],
                voice=voice,
                speed=speed
            ))
            
    # Return agent back to idle
    await manager.broadcast({"type": "agent_state", "state": "idle"})
    
    response_payload = {
        "text": result["text"],
        "spoken_text": result["spoken_text"],
        "actions": result["actions"],
        "source": result["source"],
        "message_id": result["message_id"],
        "timestamp": result["timestamp"],
        "audio_base64": audio_base64
    }
    
    # Broadcast to all connected clients
    await manager.broadcast({
        "type": "new_message",
        "session_id": req.session_id,
        "data": response_payload
    })
    
    return response_payload

@app.post("/api/voice/listen")
async def trigger_listen():
    """Triggers server microphone listening and transcription."""
    await manager.broadcast({"type": "agent_state", "state": "listening"})
    text = await asyncio.to_thread(listen_and_transcribe_mic)
    await manager.broadcast({"type": "agent_state", "state": "idle"})
    return {"text": text}

@app.post("/api/voice/tts")
async def tts_endpoint(req: TTSRequest):
    """Generates WAV audio for given text and returns as audio/wav response."""
    wav_bytes = await asyncio.to_thread(
        synthesize_wav_bytes,
        text=req.text,
        voice=req.voice,
        speed=req.speed
    )
    if not wav_bytes:
        raise HTTPException(status_code=500, detail="Voice synthesis failed or voice engine unavailable")
        
    return Response(content=wav_bytes, media_type="audio/wav")

@app.post("/api/voice/transcribe")
async def transcribe_upload(file: UploadFile = File(...)):
    """Transcribes uploaded audio file from browser."""
    content = await file.read()
    text = await asyncio.to_thread(transcribe_audio_stream, content)
    return {"text": text}

@app.post("/api/actions/execute")
async def execute_action_endpoint(req: ActionExecuteRequest):
    """Executes a custom shell action or tool."""
    res = await asyncio.to_thread(execute_shell_command, req.command)
    return res

# WebSocket Hub
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    # Send initial welcome state & telemetry
    try:
        telemetry = get_system_telemetry()
        config = load_config()
        await websocket.send_json({
            "type": "init",
            "telemetry": telemetry,
            "config": config,
            "agent_state": "idle"
        })
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "set_state":
                state = data.get("state", "idle")
                await manager.broadcast({"type": "agent_state", "state": state})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)

# Serve Frontend static assets
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

@app.get("/")
async def root_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "AI Agent Server Online. Frontend files are being initialized."}


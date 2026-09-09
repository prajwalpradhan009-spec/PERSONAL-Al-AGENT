# 🤖 AI Voice Agent Platform v2.0 (Jarvis / Cyber Neural HUD)

An autonomous, multi-modal AI Voice Agent equipped with a futuristic animated Web HUD, interactive 3D Neural Orb visualizer, speech recognition (Faster-Whisper), voice synthesis (Kokoro TTS), tool & action execution engine, real-time telemetry streaming, and flexible Ollama LLM connectivity.

![AI Agent Banner](https://img.shields.io/badge/AI_Agent-v2.0_HUD-00f0ff?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi)
![Faster Whisper](https://img.shields.io/badge/Faster_Whisper-STT-blue?style=for-the-badge)
![Kokoro TTS](https://img.shields.io/badge/Kokoro-TTS_Voice-purple?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-LLM_Brain-black?style=for-the-badge&logo=ollama)

---

## 🌟 Key Features

### 1. 🌌 Animated 3D Neural Orb & Waveform Visualizer

- **Interactive 3D Canvas Sphere**: Over 400 mathematical geodesic particles that rotate, pulse, tilt, and react to mouse hovering, dragging, and shockwave clicks.
- **Dynamic State Engine**: Visually morphs in real-time between operational states:
  - 🔵 **IDLE**: Soothing cyan/indigo breathing particle field.
  - 🟢 **LISTENING**: Real-time microphone audio frequency spectrum flares & glowing acoustic ring.
  - 🟣 **THINKING / SYNTHESIZING**: High-velocity vortex spinning inward with photon particle trails.
  - 🟡 **EXECUTING ACTION**: Cybernetic orange/amber energy rings and spark bursts.
  - ⚪ **SPEAKING**: Resonant harmonic sine waves synchronized to Kokoro synthesized voice.

### 2. ⚙️ Expanded Tool & Action Execution Engine ("The Hands")

The AI Agent can directly execute commands and tools on your Windows machine:

- **Application Launcher**: Open VS Code, Notepad, Calculator, Spotify, Chrome/Edge, File Explorer, Terminal, Task Manager, Settings.
- **System Telemetry & Health Diagnostics**: Instant CPU usage, RAM utilization, Disk space, Battery percentage, Uptime, and OS details.
- **Web Search & Navigation**: Direct Google and DuckDuckGo queries, URL navigation in your browser.
- **File Management & Notes**: Fast note taking to `agent_notes.txt`, directory listing, and workspace inspection.
- **Custom Shell Execution**: Run PowerShell or Windows commands with live stdout/stderr capture, execution time measurement, and return codes.
- **Safety Modes**: Toggle between automatic execution or manual approval for commands.

### 3. 🎙️ Dual-Channel Voice & Audio Architecture

- **Speech-to-Text (STT)**: High-speed local `Faster-Whisper` transcription (`base.en` int8) with ambient noise suppression + Web Speech API fallback.
- **Text-to-Speech (TTS)**: `Kokoro` 82M neural model generating 24 kHz studio-quality audio with switchable voice personas:
  - `af_heart` (Warm American Female - Default)
  - `af_bella` (Clear American Female)
  - `af_nicole` (Soft American Female)
  - `am_adam` (Deep American Male)
  - `am_michael` (Crisp American Male)
  - `bf_emma` (British Female)
  - `bf_isabella` (British Soft Female)
- **Audio Output Target**: Stream directly to the web browser with inline audio waveform players or play through local computer speakers via `sounddevice`.

### 4. 🧠 Multi-Turn Intelligence & Personas

- **Ollama Brain Integration**: Seamlessly connect to your partner IP or local Ollama server (`http://<IP>:11434`). Auto-detects installed models.
- **Built-in Offline Intelligence**: If the Ollama server is offline or unreachable, the agent automatically switches to an internal rule-based intent engine so all system actions, app launches, calculations, and diagnostic queries continue to function without interruption!
- **Switchable Personas**:
  - 🤖 **J.A.R.V.I.S.** (Tony Stark's intelligent AI assistant)
  - ⚡ **NEO-AI** (Cyberpunk neural operator)
  - 💻 **CodeMaster AI** (Senior engineer and coding copilot)
  - ✨ **Aura** (Warm, supportive conversational companion)

### 5. 📊 Live System Telemetry HUD Drawer

- Real-time CPU, RAM, Disk, and Network I/O gauges streamed via WebSockets.
- Battery charging indicator and system uptime timer.
- Live event console displaying STT logs, prompt latency, tool outputs, and network activities.

---

## 📁 Project Structure

```
AI AGENT/
├── app/
│   ├── __init__.py
│   ├── server.py             # FastAPI backend with WebSockets & REST endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py         # Persistent configuration & personas
│   │   ├── telemetry.py      # Real-time system metrics (CPU, RAM, Disk, Net)
│   │   ├── tools.py          # Action execution engine & app launcher
│   │   ├── voice_engine.py   # Faster-Whisper STT & Kokoro TTS integration
│   │   └── llm_client.py     # Ollama client, session memory & offline engine
│   └── static/
│       ├── index.html        # Animated Glassmorphic Cyberpunk HUD
│       ├── css/
│       │   └── style.css     # Glowing neon aesthetics & responsive layouts
│       └── js/
│           ├── orb_visualizer.js   # 3D Canvas particle sphere & waveform visualizer
│           ├── audio_controller.js # Web Audio API analyzer & speech recording
│           └── app.js              # State manager, chat feed & WebSocket client
├── assistant_client.py       # Standalone terminal CLI client
├── run.py                    # One-click launcher (starts server + opens browser)
├── mic_test.py               # Microphone diagnostic test
├── test_voice.py             # TTS speech synthesis test
├── config.json               # Auto-saved user settings
└── README.md                 # Project documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+ (Virtual environment in `.venv`)
- (Optional) [Ollama](https://ollama.ai) installed locally or on your partner's network machine

### 2. Launch the Animated Web HUD (Recommended)

Run the one-click launcher:

```powershell
.\.venv\Scripts\python.exe run.py
```

This starts the FastAPI server and automatically opens **`http://127.0.0.1:8000`** in your browser!

### 3. Run in Terminal CLI Mode (Optional)

If you prefer interacting strictly from the command line:

```powershell
.\.venv\Scripts\python.exe assistant_client.py
```

---

## 🎮 How to Use

1. **Voice Interaction**:
   - Click the **Mic button** (or toggle **Auto Listen**) and speak.
   - The 3D Neural Orb will illuminate in green during speech, transition to purple while processing, and pulse in cyan while Kokoro synthesizes and speaks the response.
2. **Text Commands**:
   - Type in the input box at the bottom and press `Enter`.
3. **Example Voice & Text Commands**:
   - `"Open VS Code"`
   - `"Open Calculator"`
   - `"Show system specs and memory usage"`
   - `"Search Google for latest AI news"`
   - `"Take a note: Meeting tomorrow at 10 AM"`
   - `"List files in workspace"`
   - `"What time is it?"`
   - `"What is 45 * 180 / 3?"`
4. **Customizing Settings**:
   - Click the ⚙️ **Settings** button in the header.
   - Enter your partner's Ollama IP (e.g. `192.168.31.48`), click **Detect Models**, and select your model.
   - Change your TTS Voice (`af_heart`, `am_adam`, `bf_emma`, etc.) and speech speed.
   - Save your configuration.

---

## 🔌 API Reference

| Method | Endpoint            | Description                                              |
| ------ | ------------------- | -------------------------------------------------------- |
| `GET`  | `/api/health`       | Service health check                                     |
| `GET`  | `/api/config`       | Retrieve current configuration                           |
| `POST` | `/api/config`       | Update settings and save to `config.json`                |
| `GET`  | `/api/system/stats` | Real-time CPU, RAM, Disk, Network telemetry              |
| `GET`  | `/api/models`       | Check Ollama status and list available models            |
| `POST` | `/api/chat`         | Send user prompt and receive AI response + actions       |
| `POST` | `/api/voice/tts`    | Synthesize speech text to WAV audio stream               |
| `POST` | `/api/voice/listen` | Trigger microphone recording and Whisper STT             |
| `WS`   | `/ws`               | Real-time bidirectional streaming for states & telemetry |

---

## 🛡️ Technology Stack

- **Backend**: FastAPI, Uvicorn, WebSockets, Pydantic, Psutil
- **Voice Intelligence**: Faster-Whisper, Kokoro TTS, SoundDevice, SpeechRecognition
- **Frontend**: HTML5 Canvas 3D Particle Physics, Web Audio API, Modern Glassmorphic CSS3, Marked.js, FontAwesome

---

Enjoy your new AI Voice Assistant Platform! 🚀🤖

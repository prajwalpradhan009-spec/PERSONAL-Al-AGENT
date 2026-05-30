# AI Voice Agent

A voice-enabled AI assistant that listens to user input, processes it through a custom AI model, and responds with synthesized speech. This project combines speech recognition, text-to-speech, and large language models for a seamless conversational experience.

## 🎯 Features

- **Speech-to-Text (STT)**: Uses Faster Whisper for accurate audio transcription
- **Text-to-Speech (TTS)**: Kokoro voice synthesis for natural-sounding responses
- **AI Processing**: Integrates with Ollama for custom AI model responses
- **Microphone Input**: Real-time audio capture and processing
- **Ambient Noise Handling**: Automatic adjustment for background noise

## 📁 Project Structure

```
AI AGENT/
├── assistant_client.py      # Main AI agent client with voice I/O
├── mic_test.py             # Microphone functionality test
├── test_voice.py           # Text-to-speech voice synthesis test
├── hello.txt               # Sample text file
└── README.md              # This file
```

## 🔧 Files Description

### `assistant_client.py`

Main application file that orchestrates the entire voice conversation flow:

- **Listen & Transcribe**: Captures audio from microphone and converts to text using Whisper
- **Process**: Sends transcribed text to Ollama AI model for processing
- **Respond**: Generates audio response using Kokoro TTS and plays it back

Configuration:

- `PARTNER_IP`: IP address of the Ollama server
- `OLLAMA_MODEL`: Custom AI model name (e.g., "MyCustomAI")

### `mic_test.py`

Quick diagnostic tool to verify microphone functionality:

- Tests microphone connectivity
- Performs speech recognition using Google's API
- Useful for troubleshooting audio input issues

### `test_voice.py`

Voice synthesis test script:

- Tests Kokoro TTS voice generation
- Plays a sample message through speakers
- Verifies audio output is working correctly

## 📦 Dependencies

The project requires the following Python packages:

```
sounddevice          # Audio playback
speech_recognition   # Microphone input
faster-whisper       # Speech-to-text (Whisper model)
kokoro               # Text-to-speech voice synthesis
requests             # HTTP requests to Ollama
```

These are typically installed in a virtual environment (`.venv`).

## 🚀 Setup & Installation

1. **Create Virtual Environment** (if not already done):

   ```powershell
   python -m venv .venv
   ```

2. **Activate Virtual Environment**:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**:

   ```bash
   pip install sounddevice speech_recognition faster-whisper kokoro requests
   ```

4. **Install Ollama** (AI Model Server):
   - Download from [ollama.ai](https://ollama.ai)
   - Install your custom AI model or use a default one

5. **Configure Partner IP**:
   - Update `PARTNER_IP` in `assistant_client.py` with your Ollama server's IP address
   - Update `OLLAMA_MODEL` to match your installed model name

## 🎮 Usage

### Run Microphone Test

```powershell
python mic_test.py
```

Verify your microphone is working and can capture audio.

### Test Voice Synthesis

```powershell
python test_voice.py
```

Check that text-to-speech and audio playback work correctly.

### Run AI Agent

```powershell
python assistant_client.py
```

Start the voice-enabled AI assistant. Speak into your microphone, and the AI will respond with synthesized voice.

## ⚙️ Configuration

Edit `assistant_client.py` to customize:

```python
PARTNER_IP = "192.168.31.48"      # Change to your Ollama server IP
OLLAMA_ENDPOINT = f"http://{PARTNER_IP}:11434/api/generate"
OLLAMA_MODEL = "MyCustomAI"         # Change to your model name
```

## 🔊 Audio Settings

- **Microphone**: Automatically adjusted for ambient noise
- **TTS Voice**: Default is `'af_heart'` - can be changed in `test_voice.py`
- **TTS Speed**: Default is `1.0` - adjust for faster/slower speech
- **Sample Rate**: 24000 Hz for Kokoro audio

## 🐛 Troubleshooting

**Microphone not detected:**

- Run `mic_test.py` to diagnose
- Check system audio input settings

**Ollama connection error:**

- Verify Ollama is running: `ollama serve`
- Check `PARTNER_IP` matches your server
- Ensure port 11434 is accessible

**Whisper model not found:**

- Model will auto-download on first run
- First run may take several minutes

**Kokoro model download error:**

- First run will download ~82MB model
- Requires internet connection
- Subsequent runs will be instant

## 📝 Notes

- Audio processing happens in real-time with dynamic thresholds
- Temporary audio files are created and should be cleaned up
- The custom model personality is defined by the Ollama model configuration

## 🎓 Future Enhancements

- Add conversation history/memory
- Implement conversation context awareness
- Add support for multiple AI models
- Create a GUI interface
- Add logging capabilities
- Implement error recovery mechanisms

---

**Built with Whisper, Kokoro, and Ollama** 🤖🎙️

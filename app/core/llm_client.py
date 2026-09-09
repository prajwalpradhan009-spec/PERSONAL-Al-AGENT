import requests
import json
import time
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from app.core.config import PERSONAS, load_config
from app.core.tools import parse_and_execute_actions, match_rule_based_intent

class ConversationSession:
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.now().isoformat()
        
    def add_message(self, role: str, content: str, actions: List[Dict[str, Any]] = None, audio_url: str = None) -> Dict[str, Any]:
        msg = {
            "id": f"msg_{int(time.time()*1000)}",
            "role": role,
            "content": content,
            "actions": actions or [],
            "audio_url": audio_url,
            "timestamp": datetime.now().isoformat()
        }
        self.messages.append(msg)
        return msg
        
    def get_history_for_llm(self, limit: int = 10) -> List[Dict[str, str]]:
        recent = self.messages[-limit:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

# In-memory sessions store
_sessions: Dict[str, ConversationSession] = {
    "default": ConversationSession("default")
}

def get_session(session_id: str = "default") -> ConversationSession:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationSession(session_id)
    return _sessions[session_id]

def list_all_sessions() -> List[Dict[str, Any]]:
    return [
        {
            "id": s_id,
            "message_count": len(s.messages),
            "created_at": s.created_at,
            "preview": s.messages[-1]["content"][:60] if s.messages else "New conversation"
        }
        for s_id, s in _sessions.items()
    ]

def check_ollama_status(ip: str, port: int = 11434) -> Dict[str, Any]:
    """Checks if Ollama server is reachable and lists available models."""
    url = f"http://{ip}:{port}/api/tags"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            models_data = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models_data]
            return {
                "online": True,
                "url": url,
                "models": model_names,
                "count": len(model_names)
            }
    except Exception as e:
        pass
    return {
        "online": False,
        "url": url,
        "models": [],
        "count": 0
    }

def query_ollama(prompt: str, history: List[Dict[str, str]], system_prompt: str, ip: str, port: int, model: str) -> Optional[str]:
    """Sends prompt + context to Ollama server."""
    # Try /api/chat first (standard for modern Ollama with system prompt)
    chat_url = f"http://{ip}:{port}/api/chat"
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    
    chat_payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 512
        }
    }
    
    try:
        resp = requests.post(chat_url, json=chat_payload, timeout=25)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "")
    except Exception:
        pass
        
    # Fallback to legacy /api/generate
    gen_url = f"http://{ip}:{port}/api/generate"
    context_text = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in history])
    full_prompt = f"{system_prompt}\n\n{context_text}\nUser: {prompt}\nAssistant:"
    
    gen_payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False
    }
    
    try:
        resp = requests.post(gen_url, json=gen_payload, timeout=25)
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        print(f"[❌] Ollama request failed: {e}")
        return None

def fallback_agent_response(prompt: str, persona_id: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Intelligent offline engine when Ollama is not connected.
    Handles general knowledge, calculations, system queries, and conversational responses.
    """
    p_lower = prompt.lower().strip()
    
    # Greetings
    if p_lower in ["hello", "hi", "hey", "good morning", "good evening", "greetings"]:
        if persona_id == "jarvis":
            return "At your service, sir. All diagnostic systems are operational. How may I assist you today?", []
        elif persona_id == "cyberpunk":
            return "Neural link active. Cyber-OS operational. State your directive.", []
        elif persona_id == "coder":
            return "Hello! CodeMaster engine ready. What project or script are we tackling today?", []
        else:
            return "Hello! I'm here and ready to help. What can I do for you?", []
            
    # Help / Capabilities query
    if any(k in p_lower for k in ["what can you do", "help", "commands", "features", "capabilities"]):
        help_text = (
            "I can assist you with a wide range of tasks:\n"
            "• **Launch Apps**: 'Open calculator', 'Open notepad', 'Open VS Code', 'Launch Spotify', 'Open Task Manager'\n"
            "• **System Telemetry**: 'Show system specs', 'Check CPU and RAM usage', 'Battery status'\n"
            "• **Web Navigation**: 'Search Google for ...', 'Open github.com'\n"
            "• **Productivity**: 'Take a note: Buy coffee', 'List workspace files', 'What time is it'\n"
            "• **Voice & Speech**: Interactive voice conversation with real-time audio visualization\n"
            "• **Custom Commands**: Execute shell scripts and system controls directly."
        )
        return help_text, []

    # Math / Calculation queries
    math_match = re.search(r"^(calculate|what is|compute)\s+([0-9\+\-\*\/\^\(\)\.\s]+)$", p_lower)
    if math_match:
        expr = math_match.group(2).strip().replace("^", "**")
        try:
            # Safe eval for numbers and basic arithmetic
            allowed = set("0123456789+-*/. ()")
            if all(c in allowed for c in expr):
                result = eval(expr)
                return f"The result of {expr} is {result}.", []
        except Exception:
            pass

    # Generic informative response
    return (
        f"I received your request: '{prompt}'. "
        f"To enable complete open-ended generative intelligence, connect your Ollama brain server "
        f"in the Settings panel. In the meantime, all local system tools, apps, and diagnostics are fully functional!"
    ), []

def process_agent_turn(
    prompt: str, 
    session_id: str = "default",
    persona_id: str = "jarvis",
    auto_execute: bool = True
) -> Dict[str, Any]:
    """
    Main processing pipeline for a user message:
    1. Checks rule-based intent
    2. Queries Ollama if available
    3. Falls back to offline engine if needed
    4. Executes actions and cleans spoken text
    5. Saves to session history
    """
    config = load_config()
    session = get_session(session_id)
    persona = PERSONAS.get(persona_id, PERSONAS["jarvis"])
    
    # Save user message
    session.add_message(role="user", content=prompt)
    
    # 1. Rule-based high-speed intent check
    rule_result = match_rule_based_intent(prompt)
    if rule_result is not None:
        spoken_text, actions = rule_result
        assistant_msg = session.add_message(
            role="assistant", 
            content=spoken_text, 
            actions=actions
        )
        return {
            "text": spoken_text,
            "spoken_text": spoken_text,
            "actions": actions,
            "source": "rule_engine",
            "message_id": assistant_msg["id"],
            "timestamp": assistant_msg["timestamp"]
        }
        
    # 2. Ollama Query
    ip = config.get("partner_ip", "192.168.31.48")
    port = config.get("ollama_port", 11434)
    model = config.get("ollama_model", "MyCustomAI")
    
    history = session.get_history_for_llm(limit=6)
    # Exclude the current user prompt from history because we pass it separately
    if history and history[-1]["content"] == prompt:
        history = history[:-1]
        
    ollama_raw_response = query_ollama(
        prompt=prompt,
        history=history,
        system_prompt=persona["system_prompt"],
        ip=ip,
        port=port,
        model=model
    )
    
    if ollama_raw_response:
        clean_text, actions = parse_and_execute_actions(ollama_raw_response, auto_execute=auto_execute)
        assistant_msg = session.add_message(
            role="assistant",
            content=ollama_raw_response,
            actions=actions
        )
        return {
            "text": ollama_raw_response,
            "spoken_text": clean_text or ollama_raw_response,
            "actions": actions,
            "source": "ollama",
            "message_id": assistant_msg["id"],
            "timestamp": assistant_msg["timestamp"]
        }
        
    # 3. Fallback Agent Engine
    fallback_text, actions = fallback_agent_response(prompt, persona_id)
    clean_text, parsed_actions = parse_and_execute_actions(fallback_text, auto_execute=auto_execute)
    all_actions = actions + parsed_actions
    
    assistant_msg = session.add_message(
        role="assistant",
        content=fallback_text,
        actions=all_actions
    )
    return {
        "text": fallback_text,
        "spoken_text": clean_text or fallback_text,
        "actions": all_actions,
        "source": "fallback_engine",
        "message_id": assistant_msg["id"],
        "timestamp": assistant_msg["timestamp"]
    }


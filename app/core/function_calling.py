"""
LLM Function Calling & Action Execution Engine (Ollama)
Forces Ollama to output structured JSON action payloads and coordinates execution across native system modules.
"""

import os
import re
import json
import requests
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from app.core.config import load_config
from app.core.app_launcher import launch_application, close_application
from app.core.task_automation import (
    lock_workstation, 
    get_detailed_telemetry, 
    execute_web_search, 
    execute_open_url, 
    execute_shell_task
)

SYSTEM_FUNCTION_CALLING_PROMPT = """You are an autonomous AI Voice Assistant operating on the user's computer.
You have direct capability to execute actions on the operating system.

When the user gives a command, you MUST respond in valid JSON matching one of the following action schemas:

1. Launch an application:
   {"action": "open_app", "target": "<app_name>", "response": "<short spoken confirmation>"}
   Examples:
   - "Open VS Code" -> {"action": "open_app", "target": "vs code", "response": "Opening Visual Studio Code for you."}
   - "Open Chrome" -> {"action": "open_app", "target": "chrome", "response": "Launching Google Chrome."}

2. Close an application / process:
   {"action": "close_app", "target": "<app_name>", "response": "<short spoken confirmation>"}
   Example:
   - "Close Notepad" -> {"action": "close_app", "target": "notepad", "response": "Closing Notepad."}

3. Lock the screen / workstation:
   {"action": "lock_screen", "response": "Locking your workstation now."}

4. Check system telemetry & hardware diagnostics (CPU, RAM, GPU, Battery):
   {"action": "system_telemetry", "response": "Checking current system telemetry."}

5. Search the web:
   {"action": "web_search", "query": "<search_query>", "response": "<short confirmation>"}

6. Open a specific website URL:
   {"action": "open_url", "url": "<url>", "response": "<short confirmation>"}

7. Run custom shell command:
   {"action": "shell_command", "command": "<cmd>", "response": "<short confirmation>"}

8. General Conversation / Questions / No action required:
   {"action": "chat", "response": "<your conversational answer>"}

IMPORTANT: Output ONLY the raw JSON object. Do not include markdown code block syntax or extra commentary.
"""

def extract_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Robust JSON extractor: handles raw JSON, markdown-wrapped JSON, and embedded JSON objects.
    """
    if not raw_text or not raw_text.strip():
        return None
        
    cleaned = raw_text.strip()
    
    # Remove markdown codeblock ```json ... ```
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Find JSON block {...}
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    return None

def fallback_intent_extractor(prompt: str) -> Dict[str, Any]:
    """
    Rule-based semantic parser used as instant fallback when Ollama is offline or generates non-JSON.
    """
    p = prompt.strip().lower()
    
    # 1. Close app
    if p.startswith("close ") or p.startswith("kill ") or p.startswith("quit ") or p.startswith("exit "):
        target = re.sub(r"^(close|kill|quit|exit)\s+", "", p).strip()
        return {
            "action": "close_app",
            "target": target,
            "response": f"Closing {target.capitalize()}."
        }

    # 2. Open app
    if p.startswith("open ") or p.startswith("launch ") or p.startswith("start "):
        target = re.sub(r"^(open|launch|start)\s+", "", p).strip()
        # Check if URL
        if target.startswith("http") or target.startswith("www.") or ".com" in target or ".org" in target:
            return {
                "action": "open_url",
                "url": target,
                "response": f"Opening {target}."
            }
        return {
            "action": "open_app",
            "target": target,
            "response": f"Opening {target.capitalize()} for you."
        }

    # 3. Lock screen
    if any(k in p for k in ["lock screen", "lock computer", "lock pc", "lock workstation"]):
        return {
            "action": "lock_screen",
            "response": "Locking your computer screen now."
        }

    # 4. Telemetry / Diagnostics
    if any(k in p for k in ["system specs", "telemetry", "cpu usage", "ram usage", "memory usage", "battery status", "diagnostics", "system status"]):
        return {
            "action": "system_telemetry",
            "response": "Here is your system telemetry."
        }

    # 5. Web Search
    search_match = re.search(r"^(search|google|lookup)\s+(for\s+)?(.+)", p)
    if search_match:
        query = search_match.group(3).strip()
        return {
            "action": "web_search",
            "query": query,
            "response": f"Searching Google for {query}."
        }

    # 6. Default conversation
    return {
        "action": "chat",
        "response": f"I received your request: '{prompt}'. All local system tools and actions are ready."
    }

def query_ollama_structured(prompt: str, history: List[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Sends prompt to Ollama requesting structured JSON output (using format='json').
    """
    config = load_config()
    ip = config.get("partner_ip", "192.168.31.48")
    port = config.get("ollama_port", 11434)
    model = config.get("ollama_model", "MyCustomAI")
    
    url = f"http://{ip}:{port}/api/chat"
    
    messages = [{"role": "system", "content": SYSTEM_FUNCTION_CALLING_PROMPT}]
    if history:
        messages.extend(history[-4:])
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 256
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=(1.2, 3.0))
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "")
            return extract_json_payload(content)
    except Exception:
        pass
        
    # Fallback /api/generate
    gen_url = f"http://{ip}:{port}/api/generate"
    gen_payload = {
        "model": model,
        "system": SYSTEM_FUNCTION_CALLING_PROMPT,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    try:
        resp = requests.post(gen_url, json=gen_payload, timeout=(1.2, 3.0))
        if resp.status_code == 200:
            content = resp.json().get("response", "")
            return extract_json_payload(content)
    except Exception:
        pass

    return None

def execute_structured_action(action_payload: Dict[str, Any], auto_execute: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Dispatches parsed JSON action to the corresponding native executor.
    Returns: (spoken_text, executed_actions_list)
    """
    action_type = action_payload.get("action", "chat")
    spoken_response = action_payload.get("response", "")
    actions_executed = []

    if not auto_execute and action_type != "chat":
        return spoken_response or "Action pending approval.", [{
            "action_type": action_type,
            "status": "pending_approval",
            "payload": action_payload,
            "timestamp": datetime.now().isoformat()
        }]

    # 1. Open App
    if action_type == "open_app":
        target = action_payload.get("target", "")
        res = launch_application(target)
        actions_executed.append({
            "action_type": "open_app",
            "command": f"launch {target}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "details": res,
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = res.get("output") or f"Could not launch {target}."

    # 2. Close App
    elif action_type == "close_app":
        target = action_payload.get("target", "")
        res = close_application(target)
        actions_executed.append({
            "action_type": "close_app",
            "command": f"close {target}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "details": res,
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = res.get("output") or f"Could not close {target}."

    # 3. Lock Screen
    elif action_type == "lock_screen":
        res = lock_workstation()
        actions_executed.append({
            "action_type": "lock_screen",
            "command": "lock_screen",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output") or res.get("error"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = "Locking your screen."

    # 4. Telemetry
    elif action_type == "system_telemetry":
        telemetry_res = get_detailed_telemetry()
        actions_executed.append({
            "action_type": "system_telemetry",
            "command": "get_telemetry",
            "status": "success",
            "output": telemetry_res["summary"],
            "telemetry": telemetry_res,
            "timestamp": datetime.now().isoformat()
        })
        spoken_response = f"System telemetry: {telemetry_res['summary']}"

    # 5. Web Search
    elif action_type == "web_search":
        query = action_payload.get("query", "")
        res = execute_web_search(query)
        actions_executed.append({
            "action_type": "web_search",
            "command": f"search {query}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = f"Searching Google for {query}."

    # 6. Open URL
    elif action_type == "open_url":
        url = action_payload.get("url", "")
        res = execute_open_url(url)
        actions_executed.append({
            "action_type": "open_url",
            "command": f"open {url}",
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = f"Opening {url}."

    # 7. Shell Command
    elif action_type == "shell_command":
        cmd = action_payload.get("command", "")
        res = execute_shell_task(cmd)
        actions_executed.append({
            "action_type": "shell_command",
            "command": cmd,
            "status": "success" if res.get("success") else "error",
            "output": res.get("output"),
            "return_code": res.get("return_code", 0),
            "timestamp": datetime.now().isoformat()
        })
        if not spoken_response:
            spoken_response = "Executed shell command."

    # 8. Chat
    else:
        if not spoken_response:
            spoken_response = action_payload.get("text", "Understood.")

    return spoken_response, actions_executed

def process_function_calling_turn(prompt: str, history: List[Dict[str, str]] = None, auto_execute: bool = True) -> Dict[str, Any]:
    """
    Main entry point:
    1. Queries Ollama for structured JSON action.
    2. Falls back to semantic intent parser if needed.
    3. Executes the structured action natively on Windows.
    """
    # 1. Try Ollama JSON Function Calling
    json_payload = query_ollama_structured(prompt, history)
    source = "ollama_json"
    
    # 2. Fallback to semantic rules
    if not json_payload:
        json_payload = fallback_intent_extractor(prompt)
        source = "rule_engine"

    # 3. Execute action
    spoken_text, actions = execute_structured_action(json_payload, auto_execute=auto_execute)

    return {
        "text": spoken_text,
        "spoken_text": spoken_text,
        "json_payload": json_payload,
        "actions": actions,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }

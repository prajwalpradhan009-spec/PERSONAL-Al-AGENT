"""
Code Writing & VS Code Automation Module
Generates code scripts, saves them to disk, and automatically opens them in VS Code.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

WORKSPACE_DIR = Path(__file__).parent.parent.parent
GENERATED_CODE_DIR = WORKSPACE_DIR / "generated_code"

LANGUAGE_EXTENSIONS = {
    "python": ".py",
    "py": ".py",
    "javascript": ".js",
    "js": ".js",
    "typescript": ".ts",
    "ts": ".ts",
    "html": ".html",
    "css": ".css",
    "cpp": ".cpp",
    "c": ".c",
    "java": ".java",
    "json": ".json",
    "markdown": ".md",
    "md": ".md",
    "sql": ".sql",
    "powershell": ".ps1",
    "ps1": ".ps1"
}

def generate_and_open_code(
    code_content: str, 
    filename: Optional[str] = None, 
    language: str = "python"
) -> Dict[str, Any]:
    """
    Saves generated code into a file and automatically opens it in VS Code ready for editing.
    """
    GENERATED_CODE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine extension and filename
    ext = LANGUAGE_EXTENSIONS.get(language.lower(), ".py")
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"script_{timestamp}{ext}"
    elif not any(filename.endswith(e) for e in LANGUAGE_EXTENSIONS.values()):
        filename = f"{filename}{ext}"

    target_path = GENERATED_CODE_DIR / filename
    
    try:
        # Write code to file
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(code_content.strip() + "\n")
            
        # Launch VS Code with target file
        subprocess.Popen(f"code \"{str(target_path)}\"", shell=True)
        
        return {
            "success": True,
            "filename": filename,
            "filepath": str(target_path),
            "language": language,
            "line_count": len(code_content.strip().splitlines()),
            "output": f"Generated '{filename}' and opened in VS Code for Founder Prajjwal."
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "error": f"Failed to save and open code in VS Code: {str(e)}"
        }

"""
File Manager Module
Creates new files/notes, reads and summarizes existing files from user storage.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

WORKSPACE_DIR = Path(__file__).parent.parent.parent

def create_text_file(filename: str, content: str) -> Dict[str, Any]:
    """Creates a new text file or note in the workspace directory."""
    target_path = WORKSPACE_DIR / filename
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "filename": filename,
            "filepath": str(target_path),
            "size_bytes": os.path.getsize(target_path),
            "output": f"Successfully created '{filename}' ({os.path.getsize(target_path)} bytes)."
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "error": f"Failed to create file: {str(e)}"
        }

def read_text_file(filepath: str, max_chars: int = 4000) -> Dict[str, Any]:
    """Reads content from a file and returns preview / full text."""
    path = Path(filepath)
    if not path.is_absolute():
        path = WORKSPACE_DIR / filepath
        
    if not path.exists():
        return {
            "success": False,
            "filepath": str(path),
            "error": f"File '{filepath}' not found."
        }

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
        line_count = len(content.splitlines())
        return {
            "success": True,
            "filepath": str(path),
            "filename": path.name,
            "content": content,
            "line_count": line_count,
            "output": f"Read {line_count} lines from '{path.name}'."
        }
    except Exception as e:
        return {
            "success": False,
            "filepath": str(path),
            "error": f"Error reading file: {str(e)}"
        }

def list_storage_files(directory: str = ".") -> Dict[str, Any]:
    """Lists files in the workspace or specified directory."""
    path = Path(directory)
    if not path.is_absolute():
        path = WORKSPACE_DIR / directory
        
    try:
        items = []
        for item in path.iterdir():
            if item.name.startswith("."):
                continue
            items.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size_kb": round(item.stat().st_size / 1024, 1) if item.is_file() else 0
            })
        return {
            "success": True,
            "directory": str(path),
            "items": items,
            "count": len(items),
            "output": f"Found {len(items)} items in '{path.name or 'workspace'}'."
        }
    except Exception as e:
        return {
            "success": False,
            "directory": str(path),
            "error": f"Failed to list directory: {str(e)}"
        }

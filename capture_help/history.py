import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

HISTORY_DIR = Path.home() / ".config" / "capture-help" / "history"

def ensure_history_dir() -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR

def save_session(session_id: str, messages: List[Dict[str, str]], title: Optional[str] = None):
    """Save session messages and metadata to JSON."""
    ensure_history_dir()
    filepath = HISTORY_DIR / f"session_{session_id}.json"
    
    if not title and messages:
        first_user_msg = next((m["content"] for m in messages if m["role"] == "user"), "Chat Session")
        title = first_user_msg[:40] + ("..." if len(first_user_msg) > 40 else "")

    data = {
        "id": session_id,
        "timestamp": time.time(),
        "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "title": title or "Chat Session",
        "turns": len(messages),
        "messages": messages,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def list_sessions() -> List[Dict[str, Any]]:
    """List all saved chat sessions sorted by timestamp descending."""
    ensure_history_dir()
    sessions = []
    for p in HISTORY_DIR.glob("session_*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                sessions.append(data)
        except Exception:
            pass
    sessions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return sessions

def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Load a specific session by ID or index."""
    ensure_history_dir()
    # Check direct filename
    filepath = HISTORY_DIR / f"session_{session_id}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    # Check numeric index (1-based from history list)
    sessions = list_sessions()
    if session_id.isdigit():
        idx = int(session_id) - 1
        if 0 <= idx < len(sessions):
            return sessions[idx]

    return None

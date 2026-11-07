import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

MEMORY_DB_PATH = Path.home() / ".config" / "capture-help" / "memory.db"
MAX_MEMORIES = 100
MAX_AUTO_CORRECTIONS = 20


def _sanitize_auto_memory(content: str) -> str:
    """Keep accidental credentials out of automatically learned memories."""
    content = re.sub(
        r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}",
        "[REDACTED_API_KEY]",
        content,
    )
    content = re.sub(r"ghp_[A-Za-z0-9]{36}", "[REDACTED_GITHUB_TOKEN]", content)
    content = re.sub(
        r"(?i)(password|secret|api[_-]?key|token)\s*[:=]\s*[\"']?[^\s\"'\n]+",
        r"\1=[REDACTED]",
        content,
    )
    return content[:300].strip()

def init_memory_db():
    """Initialize SQLite database for background learning memory."""
    MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def add_memory(category: str, content: str) -> bool:
    """Add a learned rule or user preference to memory."""
    if category == "auto_correction":
        content = _sanitize_auto_memory(content)
    content = content.strip()
    if not content:
        return False

    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        exists = conn.execute(
            "SELECT 1 FROM memory WHERE category = ? AND lower(content) = lower(?) LIMIT 1",
            (category, content),
        ).fetchone()
        if exists:
            return False
        conn.execute(
            "INSERT INTO memory (category, content, created_at) VALUES (?, ?, ?)",
            (category, content, datetime.now().isoformat())
        )
        if category == "auto_correction":
            conn.execute(
                """
                DELETE FROM memory
                WHERE category = ?
                  AND id NOT IN (
                    SELECT id FROM memory
                    WHERE category = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (category, category, MAX_AUTO_CORRECTIONS),
            )
    return True

def get_all_memories(limit: int = MAX_MEMORIES) -> List[Dict[str, str]]:
    """Fetch all active background memories and learned rules."""
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, category, content, created_at FROM memory ORDER BY id DESC LIMIT ?",
            (max(0, limit),),
        )
        rows = cursor.fetchall()
        return [{"id": r[0], "category": r[1], "content": r[2], "created_at": r[3]} for r in rows]

def clear_memories():
    """Clear memory store."""
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("DELETE FROM memory")

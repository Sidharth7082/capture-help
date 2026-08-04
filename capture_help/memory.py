import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict

MEMORY_DB_PATH = Path.home() / ".config" / "capture-help" / "memory.db"

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

def add_memory(category: str, content: str):
    """Add a learned rule or user preference to memory."""
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memory (category, content, created_at) VALUES (?, ?, ?)",
            (category, content, datetime.now().isoformat())
        )

def get_all_memories() -> List[Dict[str, str]]:
    """Fetch all active background memories and learned rules."""
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, category, content, created_at FROM memory ORDER BY id DESC")
        rows = cursor.fetchall()
        return [{"id": r[0], "category": r[1], "content": r[2], "created_at": r[3]} for r in rows]

def clear_memories():
    """Clear memory store."""
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("DELETE FROM memory")

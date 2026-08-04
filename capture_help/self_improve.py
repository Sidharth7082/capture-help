import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

PROFILE_PATH = Path.home() / ".config" / "capture-help" / "user_profile.json"
SKILLS_DIR = Path.home() / ".config" / "capture-help" / "skills"

def init_user_profile():
    """Initialize or load user persona profile."""
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    
    if not PROFILE_PATH.exists():
        default_profile = {
            "os": "Arch Linux",
            "preferred_package_manager": "pacman / yay",
            "shell": "bash / zsh",
            "coding_style": "clean, fast, minimal dependencies",
            "learned_preferences": [
                "User is running Arch Linux",
                "User prefers 100% free local models like Google Gemma 3 12B via Ollama",
                "User likes rich dark mode Catppuccin Mocha tables and visual panels"
            ],
            "last_updated": datetime.now().isoformat()
        }
        PROFILE_PATH.write_text(json.dumps(default_profile, indent=2), encoding="utf-8")

def get_user_profile() -> Dict[str, Any]:
    init_user_profile()
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def update_user_profile(key: str, value: Any):
    profile = get_user_profile()
    profile[key] = value
    profile["last_updated"] = datetime.now().isoformat()
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")

def create_auto_skill(skill_name: str, description: str, bash_script: str):
    """Save an automatically created skill script into ~/.config/capture-help/skills/."""
    init_user_profile()
    skill_file = SKILLS_DIR / f"{skill_name}.sh"
    skill_file.write_text(f"#!/usr/bin/env bash\n# Skill: {skill_name}\n# Description: {description}\n\n{bash_script}\n", encoding="utf-8")
    skill_file.chmod(0o755)

def list_auto_skills() -> List[Dict[str, str]]:
    init_user_profile()
    skills = []
    for sf in SKILLS_DIR.glob("*.sh"):
        skills.append({
            "name": sf.stem,
            "path": str(sf),
            "size": f"{sf.stat().st_size} B"
        })
    return skills

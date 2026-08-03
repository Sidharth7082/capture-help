import json
from pathlib import Path
from typing import Dict, List, Optional
from capture_help.config import settings

BUILTIN_PLUGINS: Dict[str, Dict[str, str]] = {
    "qml-glassmorphism": {
        "name": "Qt 6 QML Glassmorphism",
        "description": "Rules for Qt Quick, QML glassmorphism, dynamic animations & Quickshell IPC",
        "prompt": "You are a Qt 6 QML expert. Enforce Quickshell IPC practices, relative script url resolution (Qt.resolvedUrl), smooth spring animations, and glassmorphism styling."
    },
    "python-fastapi": {
        "name": "Python FastAPI & Async",
        "description": "Best practices for FastAPI, Pydantic v2, and async Python development",
        "prompt": "You are a senior Python backend architect. Enforce type hints, Pydantic v2 validation, async/await non-blocking design, and clean RESTful API standards."
    },
    "cmake-ninja": {
        "name": "Modern CMake & Ninja",
        "description": "Rules for CMake 3.20+, target-based builds, and Ninja generator optimization",
        "prompt": "You are a modern C++ build engineer. Enforce target_link_libraries, target_include_directories, compile warnings (-Wall -Wextra), and Ninja build optimization."
    },
    "docker-k8s": {
        "name": "Docker & Kubernetes Security",
        "description": "Container multi-stage builds, non-root execution, and security hardening",
        "prompt": "You are a DevSecOps container engineer. Enforce multi-stage Dockerfiles, distroless / alpine base images, non-root USER execution, and minimal image layer sizing."
    }
}

def get_enabled_plugins() -> List[str]:
    plugin_file = Path("~/.config/capture-help/plugins.json").expanduser()
    if not plugin_file.exists():
        return []
    try:
        with open(plugin_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_enabled_plugins(plugins: List[str]):
    plugin_file = Path("~/.config/capture-help/plugins.json").expanduser()
    plugin_file.parent.mkdir(parents=True, exist_ok=True)
    with open(plugin_file, "w", encoding="utf-8") as f:
        json.dump(plugins, f, indent=2)

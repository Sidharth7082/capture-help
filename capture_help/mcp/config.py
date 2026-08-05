"""Persistent registry of externally registered MCP servers.

Stored as JSON at ``MCP_CONFIG_FILE`` so it can be redirected to a temp
location during tests (mirrors the ``CONFIG_DIR`` pattern in ``config.py``).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from capture_help.mcp import MCP_CONFIG_FILE


def _load() -> Dict[str, Dict]:
    if not MCP_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(MCP_CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save(servers: Dict[str, Dict]) -> None:
    MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_FILE.write_text(
        json.dumps(servers, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def validate_server(server: Dict) -> Optional[str]:
    """Return an error string if the server entry is invalid, else None."""
    if not server.get("name"):
        return "server name is required"
    if not server.get("command") and not server.get("url"):
        return "server must define 'command' (argv) or 'url' (SSE/HTTP endpoint)"
    return None


def add_server(name: str, command: Optional[List[str]] = None, url: Optional[str] = None) -> None:
    """Register an external MCP server. Either a command (argv) or a url is required."""
    servers = _load()
    servers[name] = {
        "name": name,
        "command": command,
        "url": url,
        "enabled": True,
    }
    _save(servers)


def remove_server(name: str) -> bool:
    servers = _load()
    if name in servers:
        del servers[name]
        _save(servers)
        return True
    return False


def list_servers() -> Dict[str, Dict]:
    return _load()


def set_enabled(name: str, enabled: bool) -> bool:
    servers = _load()
    if name not in servers:
        return False
    servers[name]["enabled"] = bool(enabled)
    _save(servers)
    return True


def get_server(name: str) -> Optional[Dict]:
    return _load().get(name)


def enabled_servers() -> Dict[str, Dict]:
    return {k: v for k, v in _load().items() if v.get("enabled", True)}
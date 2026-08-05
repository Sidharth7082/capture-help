"""
Model Context Protocol (MCP) integration for capture-help.

Provides two directions:
- server mode: expose capture-help capabilities as MCP tools for external clients
- client mode: register external MCP servers and invoke their tools from the CLI / agent
"""

from pathlib import Path

MCP_CONFIG_FILE = Path.home() / ".config" / "capture-help" / "mcp.json"

__all__ = ["MCP_CONFIG_FILE"]
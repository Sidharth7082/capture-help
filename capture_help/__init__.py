"""
capture-help: A fast, modern terminal AI assistant powered by DeepSeek API.
"""

__app_name__ = "capture-help"


def _get_version() -> str:
    """Single source of truth is pyproject.toml; fall back for source checkouts."""
    try:
        from importlib.metadata import version
        return version(__app_name__)
    except Exception:
        return "3.3.0"


__version__ = _get_version()

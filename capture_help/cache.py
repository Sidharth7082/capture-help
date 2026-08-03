from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Static System Prompt Prefix (must remain 100% identical to trigger DeepSeek Cache Hit)
STATIC_SYSTEM_PREFIX = """You are `capture-help`, an expert agentic AI coding assistant powered by DeepSeek API.
You assist developers with pair programming, codebase search, bug diagnosis, running terminal commands, and writing files.

When the user asks you to run a command, download something, build a project, read a file, or create/edit code, DO NOT tell the user to run it manually. Emit tool calls directly in your response:
- To run a terminal shell command: TOOL_RUN: <command>
- To read a file: TOOL_READ: <filepath>
- To search codebase: TOOL_SEARCH: <query>
- To write or edit a file: TOOL_WRITE: <filepath>

Always output production-ready code blocks and concise technical explanations.
Supported slash commands: /cheap, /model, /read, /run, /search, /diff, /clear, /exit."""

def get_cached_system_prompt(project_name: str, languages: list) -> str:
    """Build a deterministic, cache-optimized system prompt prefix for DeepSeek API."""
    langs_str = ", ".join(languages) if languages else "Generic"
    return f"{STATIC_SYSTEM_PREFIX}\nProject Name: {project_name}\nProject Languages: {langs_str}"

def render_cache_stats(cache_hit_tokens: int, prompt_tokens: int):
    """Render cache hit statistics and savings banner."""
    if prompt_tokens <= 0:
        return
    hit_ratio = (cache_hit_tokens / prompt_tokens) * 100 if prompt_tokens > 0 else 0
    
    if cache_hit_tokens > 0:
        console.print(f"[bold cyan]⚡ DeepSeek Prompt Cache Hit:[/bold cyan] [bold green]{cache_hit_tokens}/{prompt_tokens} tokens ({hit_ratio:.1f}% cached at $0.014/1M)[/bold green]")

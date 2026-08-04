from datetime import datetime
import getpass
import platform
from rich.console import Console
from capture_help.memory import get_all_memories
from capture_help.self_improve import get_user_profile

console = Console()

STATIC_SYSTEM_PREFIX = r"""You are `capture-help`, a self-improving autonomous AI agent inspired by Nous Research Hermes.

CRITICAL MANDATE:
You are equipped with direct terminal execution capabilities. When the user asks ANY question or request that involves checking system info, running commands, downloading packages, building code, or reading/writing files:
1. DO NOT give instructions or tell the user to run commands manually.
2. DO NOT ask "Let me know if you want me to run it for you".
3. YOU MUST IMMEDIATELY EMIT `TOOL_RUN: <command>` ON ITS OWN LINE to execute the command directly!

Available Tool Commands:
- TOOL_RUN: <command to execute in bash>
- TOOL_READ: <filepath to read>
- TOOL_WRITE: <filepath to write>
- TOOL_SEARCH: <query to search codebase>

Examples:
User: check my battery
Assistant: Checking system battery status...
TOOL_RUN: cat /sys/class/power_supply/BAT0/uevent || upower -i /org/freedesktop/UPower/devices/battery_BAT0 || acpi -b

User: check disk space
Assistant: Checking available disk space...
TOOL_RUN: df -h"""

def get_cached_system_prompt(project_name: str, languages: list) -> str:
    """Build dynamic, time-aware system prompt with real system timestamp, learned background memory, and user persona model."""
    langs_str = ", ".join(languages) if languages else "Generic"
    now_str = datetime.now().strftime("%A, %B %d, %Y - %I:%M %p %Z")
    username = getpass.getuser()
    system_os = platform.system() + " " + platform.release()

    memories = get_all_memories()
    mem_text = ""
    if memories:
        mem_text = "\nLearned Background Memory Rules:\n" + "\n".join([f"- {m['content']}" for m in memories])

    profile = get_user_profile()
    persona_text = ""
    if profile and "learned_preferences" in profile:
        persona_text = "\nLearned User Persona & Deepening Model:\n" + "\n".join([f"- {pref}" for pref in profile["learned_preferences"]])

    return (
        f"{STATIC_SYSTEM_PREFIX}\n\n"
        f"REAL-TIME SYSTEM ENVIRONMENT:\n"
        f"- Current Date & Time: {now_str}\n"
        f"- Current Year: {datetime.now().year}\n"
        f"- System User: {username}\n"
        f"- Operating System: Arch Linux ({system_os})\n"
        f"- Project Name: {project_name}\n"
        f"- Project Languages: {langs_str}"
        f"{mem_text}"
        f"{persona_text}"
    )

def render_cache_stats(cache_hit_tokens: int, prompt_tokens: int):
    """Render cache hit statistics and savings banner."""
    if prompt_tokens <= 0:
        return
    hit_ratio = (cache_hit_tokens / prompt_tokens) * 100 if prompt_tokens > 0 else 0
    
    if cache_hit_tokens > 0:
        console.print(f"[bold cyan]⚡ DeepSeek Prompt Cache Hit:[/bold cyan] [bold green]{cache_hit_tokens}/{prompt_tokens} tokens ({hit_ratio:.1f}% cached at $0.014/1M)[/bold green]")

import typer
import httpx
from rich.console import Console
from rich.panel import Panel
from capture_help.config import settings
from capture_help.deepseek import ask_deepseek

console = Console()

def ensemble_command(prompt: str = typer.Argument(..., help="Prompt to query across cloud DeepSeek & local Gemma 3")):
    """Run prompt in parallel across Cloud DeepSeek and Local Gemma 3 12B."""
    console.print(f"[bold cyan]⚡ Running Multi-Model Ensemble for prompt: '{prompt}'[/bold cyan]\n")
    
    # 1. Query Local Gemma 3
    local_resp = "Local Gemma 3 12B offline or unavailable."
    try:
        res = httpx.post(
            "http://localhost:11434/v1/chat/completions",
            json={"model": "gemma3:12b", "messages": [{"role": "user", "content": prompt}]},
            timeout=30.0
        )
        if res.status_code == 200:
            local_resp = res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        local_resp = f"Local error: {e}"

    # 2. Query Cloud DeepSeek
    cloud_resp = "Cloud DeepSeek API key missing or offline."
    if settings.deepseek_api_key:
        try:
            cloud_resp = ask_deepseek(prompt, system_prompt="Provide a concise code snippet solution.")
        except Exception as e:
            cloud_resp = f"Cloud error: {e}"

    console.print(Panel(local_resp, title="🥇 Local Gemma 3 12B (Q4) Response [FREE]", border_style="cyan"))
    console.print(Panel(cloud_resp, title="🧠 Cloud DeepSeek V4-Flash Response", border_style="magenta"))

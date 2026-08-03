from typing import Optional
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table

from capture_help.config import settings, save_config
from capture_help.utils import print_header

console = Console()

def config_command(
    key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
):
    """Configure or view DeepSeek API credentials and settings."""
    print_header("Configuration Manager", "Set up DeepSeek API key & endpoint")

    if key or base_url or model:
        api_key = key or settings.deepseek_api_key
        url = base_url or settings.deepseek_base_url
        mdl = model or settings.deepseek_model
        
        cfg_path = save_config(api_key=api_key, base_url=url, model=mdl)
        console.print(f"[bold green]✓ Configuration saved successfully to:[bold white] {cfg_path}[/bold white]")
        return

    # Interactive configuration prompt if no flags supplied
    table = Table(title="Current Configuration", border_style="cyan", expand=True)
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value", style="bold white")

    masked_key = (settings.deepseek_api_key[:6] + "..." + settings.deepseek_api_key[-4:]) if len(settings.deepseek_api_key) > 10 else "(Not Set)"
    table.add_row("DEEPSEEK_API_KEY", masked_key)
    table.add_row("DEEPSEEK_BASE_URL", settings.deepseek_base_url)
    table.add_row("DEEPSEEK_MODEL", settings.deepseek_model)
    table.add_row("DEFAULT_PROVIDER", settings.default_provider)

    console.print(table)
    console.print()

    new_key = Prompt.ask("[bold yellow]Enter DeepSeek API Key[/bold yellow] (press Enter to keep current)", default=settings.deepseek_api_key or "").strip()
    new_url = Prompt.ask("[bold yellow]Enter DeepSeek Base URL[/bold yellow]", default=settings.deepseek_base_url).strip()
    new_model = Prompt.ask("[bold yellow]Enter DeepSeek Model[/bold yellow]", default=settings.deepseek_model).strip()

    if new_key:
        cfg_path = save_config(api_key=new_key, base_url=new_url, model=new_model)
        console.print(f"\n[bold green]✓ Successfully saved configuration to:[bold white] {cfg_path}[/bold white]")
    else:
        console.print("[dim]No changes saved.[/dim]")

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.config import settings, save_config
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.utils import print_header

console = Console()

def list_models_command():
    """List available official DeepSeek models and their pricing."""
    print_header("Model Selector", "Available Official DeepSeek Models & Token Costs")

    table = Table(title="🤖 Official DeepSeek Models", border_style="cyan", expand=True)
    table.add_column("Model Key", style="bold yellow")
    table.add_column("Model Name", style="bold white")
    table.add_column("Active", style="bold green")
    table.add_column("Input Cost (per 1M)", style="green")
    table.add_column("Cache Hit Cost (per 1M)", style="bold cyan")
    table.add_column("Description", style="dim white")

    for key, data in DEEPSEEK_MODELS.items():
        is_active = "[bold green]✓ Active[/bold green]" if key == settings.deepseek_model else ""
        table.add_row(
            key,
            data["name"],
            is_active,
            f"${data['input_cost_per_m']:.2f}",
            f"${data['cache_cost_per_m']:.3f}",
            data["description"],
        )

    console.print(table)
    console.print("\n[dim]To switch active model, run: [bold white]capture-help model <model_key>[/bold white][/dim]")
    console.print("[dim]For ultra-low-cost fast queries, set model to: [bold white]deepseek-v4-flash[/bold white][/dim]")

def set_model_command(model_name: str):
    """Switch active DeepSeek model."""
    p_key = model_name.lower().strip()
    if p_key not in DEEPSEEK_MODELS:
        console.print(f"[bold red]Error:[/bold red] Unknown model '{model_name}'. Run `capture-help models` to view available models.")
        return

    save_config(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=p_key,
    )
    console.print(Panel(
        f"[bold green]✓ Active DeepSeek Model Switched![/bold green]\n"
        f"Model: [bold white]{DEEPSEEK_MODELS[p_key]['name']} ({p_key})[/bold white]\n"
        f"Input Cost: [bold green]${DEEPSEEK_MODELS[p_key]['input_cost_per_m']:.2f} / 1M tokens[/bold green]\n"
        f"Cache Hit Cost: [bold cyan]${DEEPSEEK_MODELS[p_key]['cache_cost_per_m']:.3f} / 1M tokens[/bold cyan]",
        border_style="green",
        expand=False,
    ))

def config_command(
    key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
):
    """Configure or view DeepSeek API credentials and settings."""
    print_header("Configuration Manager")

    if key or base_url or model_name or provider:
        new_key = key if key else settings.deepseek_api_key
        new_url = base_url if base_url else settings.deepseek_base_url
        new_model = model_name if model_name else settings.deepseek_model
        new_provider = provider if provider else settings.default_provider

        save_config(api_key=new_key, base_url=new_url, model=new_model, provider=new_provider)
        console.print("[bold green]✓ Settings updated successfully![/bold green]")

    table = Table(title="⚙️ Current Configuration", border_style="cyan")
    table.add_column("Setting", style="bold yellow")
    table.add_column("Value", style="bold white")

    masked_key = f"{settings.deepseek_api_key[:6]}...{settings.deepseek_api_key[-4:]}" if settings.deepseek_api_key else "[red]Not Set[/red]"

    table.add_row("DeepSeek API Key", masked_key)
    table.add_row("DeepSeek Base URL", settings.deepseek_base_url)
    table.add_row("Active Model", f"{settings.deepseek_model} ({DEEPSEEK_MODELS.get(settings.deepseek_model, {}).get('name', 'Custom')})")
    table.add_row("Default Provider", settings.default_provider)

    console.print(table)

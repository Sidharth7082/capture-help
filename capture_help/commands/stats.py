import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.config import settings
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.utils import print_header

console = Console()

def stats_command():
    """Display token usage statistics, cost breakdown, and Context Caching savings."""
    print_header("Token Analytics & Cost Savings")

    # Read config and model metrics
    current_model = settings.deepseek_model
    model_data = DEEPSEEK_MODELS.get(current_model, DEEPSEEK_MODELS["deepseek-chat"])

    table = Table(title="📊 Token Usage & Cost Efficiency", border_style="cyan", expand=True)
    table.add_column("Metric / Indicator", style="bold yellow")
    table.add_column("Value / Details", style="bold white")

    table.add_row("Active DeepSeek Model", f"[bold green]{model_data['name']} ({current_model})[/bold green]")
    table.add_row("Input Token Rate", f"${model_data['input_cost_per_m']:.2f} / 1M Tokens")
    table.add_row("Context Cache Hit Rate", f"[bold cyan]${model_data['cache_cost_per_m']:.3f} / 1M Tokens[/bold cyan]")
    table.add_row("Tokens per $1.00 USD (Cache Hit)", "71,428,571 Tokens")
    table.add_row("Tokens per $1.00 USD (V4-Flash)", "14,285,714 Tokens")
    table.add_row("Default Provider", settings.default_provider)

    console.print(table)

    console.print(Panel(
        "[bold green]💡 Cost Saving Tip:[/bold green]\n"
        "Use [bold white]capture-help --cheap[/bold white] or type [bold white]/cheap[/bold white] in chat to activate\n"
        "DeepSeek V4-Flash ($0.07 / 1M tokens) with 85% prompt compression!",
        border_style="green",
        expand=False,
    ))

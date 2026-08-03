import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from capture_help.deepseek import get_provider, DEEPSEEK_MODELS
from capture_help.utils import print_header

console = Console()

def benchmark_command():
    """Benchmark DeepSeek API latency (TTFT) and throughput (Tokens/sec)."""
    print_header("API Benchmark & Speed Profiler", "Measuring TTFT & Token Generation Speed")

    test_prompt = "Write a quick Python function that calculates prime numbers up to N."

    table = Table(title="⚡ DeepSeek API Speed Benchmark", border_style="cyan", expand=True)
    table.add_column("Model Key", style="bold yellow")
    table.add_column("Latency (TTFT)", style="bold green")
    table.add_column("Throughput (Tokens/s)", style="bold cyan")
    table.add_column("Total Tokens", style="white")

    for model_key in ["deepseek-v4-flash", "deepseek-chat"]:
        provider = get_provider(model=model_key)
        start_time = time.time()
        ttft = None
        token_count = 0

        try:
            gen = provider.stream_completion(messages=[{"role": "user", "content": test_prompt}])
            for chunk, stats in gen:
                if chunk and ttft is None:
                    ttft = time.time() - start_time
                if chunk:
                    token_count += len(chunk.split())

            duration = time.time() - start_time
            tps = (token_count / duration) if duration > 0 else 0
            ttft_str = f"{ttft*1000:.0f} ms" if ttft else "N/A"

            table.add_row(model_key, ttft_str, f"{tps:.1f} tok/s", str(token_count))
        except Exception as e:
            table.add_row(model_key, "Error", "Error", str(e))

    console.print(table)

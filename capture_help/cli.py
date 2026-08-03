import typer
from typing import Optional
from pathlib import Path

from capture_help import __version__, __app_name__
from capture_help.commands.chat import chat_command
from capture_help.commands.explain import explain_command
from capture_help.commands.fix import fix_command
from capture_help.commands.review import review_command
from capture_help.commands.docs import docs_command
from capture_help.commands.commit import commit_command
from capture_help.commands.test import test_command
from capture_help.commands.optimize import optimize_command
from capture_help.commands.config_cmd import config_command

app = typer.Typer(
    name=__app_name__,
    help="⚡ capture-help: A fast, modern terminal AI assistant powered by DeepSeek API.",
    add_completion=False,
    rich_markup_mode="rich",
)

def version_callback(value: bool):
    if value:
        typer.echo(f"{__app_name__} version {__version__}")
        raise typer.Exit()

@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    )
):
    """
    ⚡ capture-help CLI: AI-powered developer assistant in your Linux terminal.
    """
    pass

@app.command("chat")
def chat():
    """Start an interactive AI chat session in the terminal."""
    chat_command()

@app.command("explain")
def explain(
    filepath: str = typer.Argument(..., help="Path to source file or build log (e.g. build.log).")
):
    """Explain a source file or compiler/build log in plain English."""
    explain_command(filepath)

@app.command("fix")
def fix(
    filepath: str = typer.Argument(..., help="Path to source file to diagnose and fix.")
):
    """Analyze a source file and suggest fixes for bugs and smells."""
    fix_command(filepath)

@app.command("review")
def review(
    target: str = typer.Argument(..., help="Path to file or directory for code review.")
):
    """Perform an automated code review on a file or directory with project summary metrics."""
    review_command(target)

@app.command("docs")
def docs(
    filepath: str = typer.Argument(..., help="Path to source file to generate documentation for.")
):
    """Generate technical documentation and docstrings for a source file."""
    docs_command(filepath)

@app.command("commit")
def commit():
    """Read git diff and generate a Conventional Commit message."""
    commit_command()

@app.command("test")
def test(
    filepath: str = typer.Argument(..., help="Path to source file to generate unit tests for.")
):
    """Generate unit tests for a source file."""
    test_command(filepath)

@app.command("optimize")
def optimize(
    filepath: str = typer.Argument(..., help="Path to source file to analyze for performance & memory gains.")
):
    """Suggest performance & memory optimizations with Big-O complexity analysis."""
    optimize_command(filepath)

@app.command("config")
def config(
    key: Optional[str] = typer.Option(None, "--key", "-k", help="DeepSeek API key."),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-u", help="DeepSeek API base URL."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="DeepSeek model name."),
):
    """Configure or view DeepSeek API credentials and settings."""
    config_command(key=key, base_url=base_url, model=model)

if __name__ == "__main__":
    app()

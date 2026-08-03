import typer
from typing import Optional

from capture_help import __version__, __app_name__
from capture_help.commands.chat import chat_command
from capture_help.commands.ask import ask_command
from capture_help.commands.explain import explain_command
from capture_help.commands.fix import fix_command
from capture_help.commands.review import review_command
from capture_help.commands.docs import docs_command
from capture_help.commands.commit import commit_command
from capture_help.commands.test import test_command
from capture_help.commands.optimize import optimize_command
from capture_help.commands.config_cmd import config_command
from capture_help.commands.alias import alias_command
from capture_help.commands.history_cmd import history_command, resume_command

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

@app.command("ask")
def ask(
    question: str = typer.Argument(..., help="Question about your codebase (e.g. 'Where is GlassEffect initialized?').")
):
    """Ask a question about the codebase with automatic project indexing and search."""
    ask_command(question)

@app.command("chat")
def chat():
    """Start an interactive AI chat session in the terminal."""
    chat_command()

@app.command("explain")
def explain(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file or build log (or pipe via stdin).")
):
    """Explain a source file or compiler/build log in plain English."""
    explain_command(filepath)

@app.command("fix")
def fix(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin).")
):
    """Analyze code and suggest fixes with interactive diff patching."""
    fix_command(filepath)

@app.command("review")
def review(
    target: Optional[str] = typer.Argument(None, help="Path to file/directory or pipe git diff via stdin.")
):
    """Perform an automated code review on a file, directory, or piped git diff."""
    review_command(target)

@app.command("docs")
def docs(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin).")
):
    """Generate technical documentation and docstrings."""
    docs_command(filepath)

@app.command("commit")
def commit():
    """Read git diff or stdin and generate a Conventional Commit message."""
    commit_command()

@app.command("test")
def test(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin).")
):
    """Generate unit tests for a source file."""
    test_command(filepath)

@app.command("optimize")
def optimize(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin).")
):
    """Suggest performance & memory optimizations with Big-O complexity analysis."""
    optimize_command(filepath)

@app.command("alias")
def alias(
    install: bool = typer.Option(False, "--install", "-i", help="Automatically install aliases into ~/.bashrc and ~/.zshrc.")
):
    """Generate or install shell aliases (ai, aifix, aireview, aidoc, aicommit, aiask)."""
    alias_command(install=install)

@app.command("history")
def history():
    """List recent saved terminal chat sessions."""
    history_command()

@app.command("resume")
def resume(
    session_id: str = typer.Argument(..., help="Session ID or history index number to resume.")
):
    """Resume a previous chat session by ID or index number."""
    resume_command(session_id)

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

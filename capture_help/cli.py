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
from capture_help.commands.doctor import doctor_command
from capture_help.commands.config_cmd import config_command, list_models_command, set_model_command
from capture_help.commands.alias import alias_command
from capture_help.commands.history_cmd import history_command, resume_command
from capture_help.commands.hook import hook_command
from capture_help.commands.index_cmd import index_command
from capture_help.commands.plugin_cmd import plugin_command
from capture_help.commands.tui import tui_command
from capture_help.commands.stats import stats_command
from capture_help.commands.web import web_command
from capture_help.commands.team import team_command

app = typer.Typer(
    name=__app_name__,
    help="⚡ capture-help v2.2.0: A fast, modern terminal AI assistant powered by DeepSeek API.",
    add_completion=False,
    rich_markup_mode="rich",
)

def version_callback(value: bool):
    if value:
        typer.echo(f"{__app_name__} version {__version__}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
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
    ⚡ capture-help v2.2.0 CLI: AI-powered developer assistant in your Linux terminal.
    """
    if ctx.invoked_subcommand is None:
        chat_command()

@app.command("stats")
def stats():
    """Display token usage analytics, cost breakdowns, and Context Caching savings."""
    stats_command()

@app.command("web")
def web(
    query: str = typer.Argument(..., help="Documentation or web search query.")
):
    """Search live web documentation and frameworks."""
    web_command(query)

@app.command("team")
def team(
    goal: str = typer.Argument(..., help="Goal or project task for the multi-agent team.")
):
    """Launch multi-agent teamwork workflow with Architect, Coder, Tester, and Security Auditor."""
    team_command(goal)

@app.command("tui")
def tui():
    """Launch interactive Rich Terminal User Interface dashboard."""
    tui_command()

@app.command("plugin")
def plugin(
    action: str = typer.Argument("list", help="Action: 'list', 'enable', 'disable'."),
    name: Optional[str] = typer.Argument(None, help="Plugin name (e.g. qml-glassmorphism, python-fastapi).")
):
    """Manage domain-specific plugins and rule packages."""
    plugin_command(action=action, plugin_name=name)

@app.command("doctor")
def doctor():
    """Run environment, configuration, dependency, and API connectivity diagnostics."""
    doctor_command()

@app.command("ask")
def ask(
    question: str = typer.Argument(..., help="Question about your codebase (e.g. 'Where is GlassEffect initialized?')."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy response to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Markdown response to specified file."),
):
    """Ask a question about the codebase with automatic project indexing and context size indicators."""
    ask_command(question, copy=copy, export=export)

@app.command("chat")
def chat():
    """Start an interactive AI chat session in the terminal."""
    chat_command()

@app.command("index")
def index():
    """Index repository files into local SQLite search database for sub-second context lookups."""
    index_command()

@app.command("hook")
def hook(
    action: str = typer.Argument("install", help="Action: 'install' or 'uninstall'.")
):
    """Install or uninstall Git pre-commit security review hook."""
    hook_command(action=action)

@app.command("explain")
def explain(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file or build log (or pipe via stdin)."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy output to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Markdown output to file."),
):
    """Explain a source file or compiler/build log in plain English."""
    explain_command(filepath, copy=copy, export=export)

@app.command("fix")
def fix(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin)."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy fixed output to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Markdown output to file."),
):
    """Analyze code and suggest fixes with interactive diff patching."""
    fix_command(filepath, copy=copy, export=export)

@app.command("review")
def review(
    target: Optional[str] = typer.Argument(None, help="Path to file/directory or pipe git diff via stdin."),
    staged: bool = typer.Option(False, "--staged", help="Review staged git changes (git diff --staged)."),
    ref: Optional[str] = typer.Option(None, "--ref", "-r", help="Git ref to review (e.g. HEAD~3, origin/main)."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy review output to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Markdown review to file."),
):
    """Perform an automated code review on a file, directory, or git ref (--staged, HEAD~3, origin/main)."""
    review_command(target, staged=staged, ref=ref, copy=copy, export=export)

@app.command("docs")
def docs(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file (or pipe via stdin)."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy documentation to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Markdown docs to file."),
):
    """Generate technical documentation and docstrings."""
    docs_command(filepath, copy=copy, export=export)

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

@app.command("models")
def models():
    """List available DeepSeek AI models."""
    list_models_command()

@app.command("model")
def model(
    model_name: str = typer.Argument(..., help="Model name to activate (e.g. deepseek-chat, deepseek-v4-flash, deepseek-reasoner).")
):
    """Switch the active DeepSeek model."""
    set_model_command(model_name)

@app.command("config")
def config(
    key: Optional[str] = typer.Option(None, "--key", "-k", help="DeepSeek API key."),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-u", help="DeepSeek API base URL."),
    model_name: Optional[str] = typer.Option(None, "--model", "-m", help="DeepSeek model name."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Provider name (deepseek, ollama)."),
):
    """Configure or view DeepSeek / Ollama API credentials and settings."""
    config_command(key=key, base_url=base_url, model=model_name)

if __name__ == "__main__":
    app()

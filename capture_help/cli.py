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
from capture_help.commands.pr import pr_command
from capture_help.commands.audit import audit_command
from capture_help.commands.diagram import diagram_command
from capture_help.commands.script import script_command
from capture_help.commands.clean import clean_command
from capture_help.commands.changelog import changelog_command
from capture_help.commands.benchmark import benchmark_command
from capture_help.commands.refactor import refactor_command
from capture_help.commands.secrets import secrets_command
from capture_help.commands.translate import translate_command
from capture_help.commands.local_cmd import app as local_app
from capture_help.commands.gpu import gpu_command
from capture_help.commands.ensemble import ensemble_command
from capture_help.commands.redact import redact_command
from capture_help.commands.update_cmd import update_command
from capture_help.commands.graph import graph_command
from capture_help.commands.guard import guard_command

app = typer.Typer(
    name=__app_name__,
    help="⚡ capture-help v3.0.0: The ultimate terminal AI assistant powered by DeepSeek API.",
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
    ⚡ capture-help v3.0.0 CLI: AI-powered developer assistant in your Linux terminal.
    """
    if ctx.invoked_subcommand is None:
        chat_command()

@app.command("pr")
def pr(
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy PR text to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export PR description to markdown file."),
):
    """Generate GitHub Pull Request description from git diff."""
    pr_command(copy=copy, export=export)

@app.command("audit")
def audit():
    """Audit project dependencies for security vulnerabilities."""
    audit_command()

@app.command("diagram")
def diagram(
    target: Optional[str] = typer.Argument(None, help="Path to source file or pipe via stdin."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy Mermaid code to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export Mermaid code to markdown file."),
):
    """Generate Mermaid architecture diagram for code file or stdin."""
    diagram_command(target, copy=copy, export=export)

@app.command("script")
def script(
    task: str = typer.Argument(..., help="Automation task description.")
):
    """Generate production-ready Bash automation script."""
    script_command(task)

@app.command("clean")
def clean(
    filepath: Optional[str] = typer.Argument(None, help="Path to source file or stdin.")
):
    """Scan file for dead code, unused imports, and redundant logic."""
    clean_command(filepath)

@app.command("changelog")
def changelog(
    export: Optional[str] = typer.Option("CHANGELOG.md", "--export", "-e", help="File to export changelog to.")
):
    """Generate GitHub-style CHANGELOG.md from git commit history."""
    changelog_command(export=export)

@app.command("benchmark")
def benchmark():
    """Benchmark DeepSeek API latency (TTFT) and throughput (Tokens/sec)."""
    benchmark_command()

@app.command("refactor")
def refactor(
    old_symbol: str = typer.Argument(..., help="Symbol to rename."),
    new_symbol: str = typer.Argument(..., help="New symbol name.")
):
    """Refactor and rename a function, variable, or class symbol across all project files."""
    refactor_command(old_symbol, new_symbol)

@app.command("secrets")
def secrets():
    """Inspect codebase for hardcoded API keys, tokens, or credentials."""
    secrets_command()

@app.command("translate")
def translate(
    filepath: str = typer.Argument(..., help="Path to source file."),
    to: str = typer.Option("cpp", "--to", "-t", help="Target programming language (cpp, rust, python, ts, go)."),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy translated code to clipboard."),
    export: Optional[str] = typer.Option(None, "--export", "-e", help="Export translated code to file."),
):
    """Translate source code from one programming language to another."""
    translate_command(filepath, to=to, copy=copy, export=export)

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

app.add_typer(local_app, name="local", help="Manage local Ollama models and local AI engine.")

@app.command("gpu")
def gpu():
    """Display GPU/VRAM hardware allocation and local inference health."""
    gpu_command()

@app.command("ensemble")
def ensemble(
    prompt: str = typer.Argument(..., help="Prompt to query across cloud DeepSeek & local Gemma 3.")
):
    """Run prompt in parallel across Cloud DeepSeek and Local Gemma 3 12B."""
    ensemble_command(prompt)

@app.command("redact")
def redact(
    text_or_file: str = typer.Argument(..., help="Text prompt or file path to redact secrets from.")
):
    """Scan and redact API keys, passwords, and IP addresses before sending prompts."""
    redact_command(text_or_file)

@app.command("update")
def update():
    """Check for new capture-help releases and updates on GitHub."""
    update_command()

@app.command("graph")
def graph():
    """Generate Mermaid.js dependency graph of codebase imports."""
    graph_command()

@app.command("guard")
def guard():
    """Run pre-push continuous security, secret, and unit test audit guard."""
    guard_command()

if __name__ == "__main__":
    app()

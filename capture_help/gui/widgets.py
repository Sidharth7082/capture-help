"""Custom Textual widgets for the Capture Help glass UI."""

import os
import re
import subprocess
import time
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.widgets import Button, Collapsible, Input, Label, OptionList, RichLog, Static, TextArea
from textual.widgets.option_list import Option
from textual.widgets._markdown import Markdown, MarkdownFence
from textual.content import Content

from capture_help import __version__
from capture_help.config import settings
from capture_help.deepseek import DEEPSEEK_MODELS
from capture_help.gui import theme

ICON = theme.ICONS

ROLE_ICONS = {
    "user": "◆",
    "assistant": "✦",
    "tool": "⚙",
    "error": "✕",
    "warning": "⚠",
    "system": "·",
}

ROLE_LABELS = {
    "user": "You",
    "assistant": "Capture Help",
    "tool": "Tool",
    "error": "Error",
    "warning": "Warning",
    "system": "System",
}

ROLE_AVATARS = {
    "user": "👤",
    "assistant": "⚡",
    "tool": "🛠",
    "error": "✕",
    "warning": "⚠",
    "system": "·",
}

# Terminal-looking names for tool/execution role subtypes
TOOL_LABELS = {
    "run": "🐚 Terminal",
    "read": "▤ File",
    "search": "⌕ Search",
    "write": "✎ Write",
    "mcp": "⇄ MCP",
}

# --------------------------------------------------------------------------- #
# Identity helpers
# --------------------------------------------------------------------------- #
def model_display_name(key: str | None = None) -> str:
    """Friendly model name, e.g. `deepseek-v4-flash` -> `DeepSeek V4 Flash`."""
    key = key or settings.deepseek_model
    data = DEEPSEEK_MODELS.get(key)
    if data:
        return data["name"]
    return key.replace("-", " ").replace(":", " ").title()


def provider_display_name() -> str:
    prov = settings.default_provider
    if prov == "ollama":
        return "Ollama (Local)"
    if prov and prov != "deepseek":
        return prov.title()
    return "DeepSeek"


TAGLINE = "Fast  •  Private  •  Open Source"


def relative_time(timestamp: float | None) -> str:
    """Human-friendly relative label like '2 min ago' / 'Yesterday'."""
    if not timestamp:
        return "recently"
    delta = time.time() - float(timestamp)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} hr ago"
    if delta < 172800:
        return "Yesterday"
    return f"{int(delta // 86400)} days ago"


def title_emoji(title: str) -> str:
    """Pick an emoji for a recent-conversation title by keyword sniffing."""
    t = (title or "").lower()
    buckets = (
        (("fix", "bug", "crash", "error"), "🐛"),
        (("refactor", "clean", "simplif", "improv"), "🔧"),
        (("build", "compile", "cmake"), "🏗"),
        (("doc", "document", "manual"), "📄"),
        (("feature", "add", "new"), "✨"),
        (("test", "unit"), "🧪"),
        (("search", "find", "lookup"), "🔍"),
        (("render", "glass", "ui", "gui"), "🎨"),
    )
    for keywords, emoji in buckets:
        if any(k in t for k in keywords):
            return emoji
    return "💬"



def workspace_summary(project: dict | None = None) -> dict:
    """Gather a lightweight 'Today's Workspace' snapshot for the landing panel.

    Returns modified-file count, last commit subject, TODO/FIXME count, a
    build status derived from git cleanliness, plus best-effort dependency and
    test-function counts. Every measurement is wrapped so it can never raise
    into the GUI.
    """
    project = project or {}
    root = Path(project.get("root") or ".")
    summary = {
        "modified": 0,
        "last_commit": None,
        "todos": 0,
        "clean": bool(project.get("git_clean", True)),
        "branch": None,
        "deps": 0,
        "tests": 0,
    }

    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True, timeout=5,
        )
        entries = [ln for ln in res.stdout.splitlines() if ln.strip()]
        summary["modified"] = len(entries)
        summary["clean"] = len(entries) == 0
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(root), capture_output=True, text=True, timeout=5,
        )
        summary["branch"] = res.stdout.strip() or None
    except Exception:
        summary["branch"] = None

    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h %s"],
            cwd=str(root), capture_output=True, text=True, timeout=5,
        )
        summary["last_commit"] = res.stdout.strip() or None
    except Exception:
        summary["last_commit"] = None

    try:
        count = 0
        exts = {".py", ".go", ".cpp", ".hpp", ".c", ".h", ".qml", ".lua", ".ts", ".js"}
        for r, dirs, files in __import__("os").walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
            for f in files:
                if not f.endswith(tuple(exts)):
                    continue
                try:
                    with open(Path(r) / f, "r", encoding="utf-8", errors="ignore") as fh:
                        for line in fh:
                            if "TODO" in line or "FIXME" in line:
                                count += 1
                except Exception:
                    continue
                if count > 9999:
                    break
            if count > 9999:
                break
        summary["todos"] = count
    except Exception:
        summary["todos"] = 0

    summary["deps"] = _count_dependencies(root)
    summary["tests"] = _count_tests(root)
    return summary


def _safe_read(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


def _count_dependencies(root: Path) -> int:
    """Best-effort dependency count across common manifests."""
    total = 0
    try:
        entries = [p for p in root.iterdir() if p.is_file()]
    except Exception:
        return 0
    try:
        for p in entries:
            name = p.name
            if name == "pyproject.toml":
                text = _safe_read(p)
                # multi-line arrays: lines that are just a quoted string
                total += len(
                    re.findall(r'^\s*["\'][^"\']+["\'],?\s*$', text, re.MULTILINE)
                )
                # inline arrays: dev = ["pytest>=7.0.0"]
                total += len(
                    re.findall(
                        r'^\s*[\w.-]+\s*=\s*\[[^\]]*["\'][^"\']+["\'][^\]]*\]\s*$',
                        text,
                        re.MULTILINE,
                    )
                )
            elif name.startswith("requirements") and name.endswith((".txt", ".in")):
                lines = [
                    ln.strip()
                    for ln in _safe_read(p).splitlines()
                    if ln.strip() and not ln.strip().startswith(("#", "-"))
                ]
                total += len(lines)
            elif name == "package.json":
                import json as _json

                data = _json.loads(_safe_read(p))
                total += len(data.get("dependencies", {})) + len(
                    data.get("devDependencies", {})
                )
            elif name == "Cargo.toml":
                text = _safe_read(p)
                in_deps = False
                for ln in text.splitlines():
                    stripped = ln.strip()
                    if stripped.startswith("["):
                        in_deps = stripped == "[dependencies]"
                        continue
                    if in_deps and stripped and not stripped.startswith(("#", "[")):
                        total += 1
            elif name == "go.mod":
                for ln in _safe_read(p).splitlines():
                    stripped = ln.strip()
                    if stripped.startswith("require ") or (
                        stripped and not stripped.startswith(("//", "module ", "go "))
                    ):
                        if stripped.startswith("require (") or stripped.startswith(")"):
                            continue
                        total += 1
    except Exception:
        pass
    return min(total, 9999)


def _count_tests(root: Path) -> int:
    """Count test functions/methods in test files (no test run required)."""
    count = 0
    try:
        for r, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
            for f in files:
                if not (f.endswith((".py", ".go")) and ("test" in f.lower() or f.startswith("test_"))):
                    continue
                for ln in _safe_read(Path(r) / f).splitlines():
                    stripped = ln.strip()
                    if "def test_" in stripped or stripped.startswith("func Test"):
                        count += 1
                    if count > 9999:
                        break
                if count > 9999:
                    break
            if count > 9999:
                break
    except Exception:
        pass
    return count

# --------------------------------------------------------------------------- #
# Diff helpers
# --------------------------------------------------------------------------- #
DIFF_LANGS = {"diff", "patch", "git-diff", "unified"}


def diff_line_style(line: str) -> str | None:
    """Rich style string for one line of a unified diff.

    File/header lines are dim bold, hunk markers are blue, additions green,
    removals red, and context lines dim — so diffs are scannable at a glance.
    """
    if line.startswith(
        ("diff --git", "index ", "--- ", "+++ ", "new file", "deleted file", "rename ")
    ):
        return "bold #8f9aa9"
    if line.startswith("@@"):
        return "bold #6aa9f0"
    if line.startswith("+"):
        return "#4ed98c"
    if line.startswith("-"):
        return "#f2556f"
    return "#5d6878"


def looks_like_diff(text: str) -> bool:
    """True when ``text`` contains unified-diff markers (git-style)."""
    lines = (text or "").splitlines()
    if any(ln.startswith("diff --git") or ln.startswith("@@ -") for ln in lines):
        return True
    plus = any(ln.startswith("+++ ") for ln in lines)
    minus = any(ln.startswith("--- ") for ln in lines)
    return plus and minus


def diff_text(content: str) -> Text:
    """Render diff-like text as a rich Text with per-line diff colours."""
    lines = (content or "").splitlines()
    text = Text()
    for i, line in enumerate(lines):
        text.append(line, style=diff_line_style(line))
        if i < len(lines) - 1:
            text.append("\n")
    return text


# --------------------------------------------------------------------------- #
# Chat widgets
# --------------------------------------------------------------------------- #
class CodeFence(MarkdownFence):
    """A code block that adds a language header bar, line numbers and
    Copy / Insert actions.

    Textual's stock fence is a plain highlighted block; this subclass wraps the
    highlighted code in a labelled card so multi-line answers are scannable.
    Fences written with a ``diff``/``patch`` language (or containing unified
    diff markers) render as a diff card: green additions, red removals, blue
    hunks, a filename header and a Copy action only.
    """

    def compose(self) -> ComposeResult:
        is_diff = self._is_diff()
        self._content_label = Label(
            self._diff_content() if is_diff else self._numbered(self._highlighted_code),
            id="code-content",
            expand=True,
        )
        with Vertical(classes="code-card diff-card" if is_diff else "code-card"):
            with Horizontal(classes="code-card-header"):
                yield Label(
                    self._diff_filename() if is_diff else self._language_label(),
                    classes="code-lang",
                )
                yield Label("", classes="status-spacer")
                self.copy_btn = Button("Copy", classes="code-btn")
                yield self.copy_btn
                if not is_diff:
                    self.insert_btn = Button("Insert", classes="code-btn")
                    yield self.insert_btn
            yield self._content_label

    def _language_label(self) -> str:
        return (self.lexer or "").strip() or "text"

    def _is_diff(self) -> bool:
        lang = (self.lexer or "").strip().lower()
        if lang in DIFF_LANGS:
            return True
        if lang:
            return False
        return looks_like_diff(self.code or "")

    def _diff_filename(self) -> str:
        """Best-effort file name for a diff header, e.g. ``Renderer.cpp``."""
        for line in (self.code or "").splitlines():
            if line.startswith("+++ "):
                name = line[4:].strip()
                if name.startswith("b/"):
                    name = name[2:]
                if name and name != "/dev/null":
                    return name
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4 and parts[3].startswith("b/"):
                    return parts[3][2:]
        return "Diff"

    def _diff_content(self) -> Content:
        """Plain text with line numbers, coloured per unified-diff semantics."""
        from textual.content import Content as _C, Span  # noqa: F401

        lines = (self.code or "").splitlines()
        width = len(str(len(lines)))
        out_lines = []
        spans = []
        offset = 0
        for i, seg in enumerate(lines, start=1):
            pfx = f"{i:>{width}} "
            line = pfx + seg
            out_lines.append(line)
            start = offset + len(pfx)
            style = diff_line_style(seg)
            if style:
                spans.append(Span(start, start + len(seg), style))
            offset += len(line) + 1
        return Content("\n".join(out_lines).rstrip("\n"), spans=spans, strip_control_codes=False)

    def _numbered(self, content: Content) -> Content:
        """Prefix each line with a dim line number while keeping highlighting."""
        from textual.content import Content as _C, Span  # noqa: F401

        text = content._text
        if not text:
            return content
        segs = text.split("\n")
        width = len(str(len(segs)))
        # new absolute offset for the start of each line's code
        new_start = []
        out_parts = []
        new_len = 0
        for i, seg in enumerate(segs, start=1):
            new_start.append(new_len)
            pfx = f"{i:>{width}} "
            out_parts.append(pfx)
            out_parts.append(seg)
            new_len += len(pfx) + len(seg) + 1  # +1 for trailing newline
        new_text = "".join(out_parts).rstrip("\n")

        def line_of(offset: int) -> int:
            idx = 0
            for ln, seg in enumerate(segs):
                if offset <= idx + len(seg):
                    return ln
                idx += len(seg) + 1
            return len(segs) - 1

        new_spans = []
        pfx_len = width + 1
        for start, end, style in content._spans:
            s_line = line_of(start)
            e_line = line_of(end)
            s_new = new_start[s_line] + pfx_len + (start - self._line_offset(segs, s_line))
            e_new = new_start[e_line] + pfx_len + (end - self._line_offset(segs, e_line))
            new_spans.append(Span(s_new, e_new, style))
        return Content(new_text, spans=new_spans, strip_control_codes=False)

    @staticmethod
    def _line_offset(segs: list, line: int) -> int:
        base = 0
        for i in range(line):
            base += len(segs[i]) + 1
        return base

    def set_content(self, content) -> None:
        label = getattr(self, "_content_label", None)
        if label is None:
            return
        if self._is_diff():
            label.update(self._diff_content())
        else:
            label.update(self._numbered(content))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Copy / Insert actions for the fence's header buttons."""
        if event.button is getattr(self, "copy_btn", None):
            event.stop()
            self.app.copy_to_clipboard(self.code or "")
            self.app.notify("Copied to clipboard")
            return
        if event.button is getattr(self, "insert_btn", None):
            event.stop()
            self._insert_into_input()

    def _insert_into_input(self) -> None:
        """Place the fence's code into the prompt input so the user can
        edit or extend it before sending."""
        try:
            inp = self.app.query_one("#prompt-input", ChatInput)
        except Exception:  # noqa: BLE001
            return
        code = (self.code or "").rstrip()
        if not code:
            return
        if inp.value:
            inp.value = inp.value.rstrip() + "\n" + code
        else:
            inp.value = code
        inp.cursor_position = len(inp.value)
        inp.focus()
        self.app.notify("Inserted into input")


class CodeMarkdown(Markdown):
    """Markdown that renders code blocks as labelled, numbered cards."""

    BLOCKS = {**Markdown.BLOCKS, "fence": CodeFence, "code_block": CodeFence}


class ChatMessage(Container):
    """A single conversation bubble.

    Roles: user / assistant / tool / error / warning / system.
    Assistant bubbles embed a Markdown widget that can be updated in place
    while tokens stream in. A role header (avatar + name) gives every bubble
    an identity, and tool messages can carry a terminal-style sub-label.
    """

    def __init__(
        self,
        role: str,
        content: str = "",
        streaming: bool = False,
        sublabel: str | None = None,
        **kwargs,
    ):
        classes = f"chat-message role-{role}"
        super().__init__(classes=classes, **kwargs)
        self.role = role
        self.content = content
        self.streaming = streaming
        self.sublabel = sublabel
        self.markdown: Markdown | None = None
        self.role_label: Label | None = None
        self.stream_preview: Static | None = None
        self._compact_pending = False

    def compose(self) -> ComposeResult:
        avatar = ROLE_AVATARS.get(self.role, "·")
        name = ROLE_LABELS.get(self.role, self.role.title())
        sub = f"  ·  {self.sublabel}" if self.sublabel else ""
        self.role_label = Label(f"{avatar}  {name}{sub}", classes="msg-role")
        yield self.role_label
        with Container(classes="bubble"):
            if self.role in ("user", "assistant"):
                if self._compact_pending:
                    yield Static(self.content or "", classes="plain-message", markup=False)
                elif self.role == "assistant" and self.streaming:
                    self.stream_preview = Static(self.content or "", classes="stream-preview")
                    yield self.stream_preview
                else:
                    self.markdown = CodeMarkdown(self.content or "")
                    yield self.markdown
            else:
                icon = ROLE_ICONS.get(self.role, "·")
                text = f"{icon} {self.content}" if self.content else icon
                if self.role == "tool" and looks_like_diff(self.content):
                    yield Static(diff_text(text), markup=False)
                else:
                    yield Static(text, markup=False)

    def update_markdown(self, text: str) -> None:
        if self.markdown is not None:
            self.markdown.update(text)

    def update_stream_preview(self, text: str) -> None:
        if self.stream_preview is not None:
            self.stream_preview.update(text)

    def finalize_stream(self, text: str) -> None:
        if self.stream_preview is None:
            self.update_markdown(text)
            return
        preview = self.stream_preview
        self.stream_preview = None
        preview.remove()
        self.markdown = CodeMarkdown(text)
        self.query_one(".bubble").mount(self.markdown)

    def compact(self) -> None:
        """Swap rich Markdown for plain text once a message is no longer recent.

        Markdown re-rendering dominates refresh cost in long chats, and older
        messages rarely need syntax highlighting, so they render as plain text.
        """
        if self._compact_pending:
            return
        self._compact_pending = True
        if self.markdown is None:
            # Not composed yet: compose() will render plain text directly.
            return
        source = self.markdown.source
        self.content = source
        self.stream_preview = None
        try:
            self.markdown.remove()
        except Exception:  # noqa: BLE001
            return
        self.markdown = None
        self.query_one(".bubble").mount(
            Static(source, classes="plain-message", markup=False)
        )


class ThinkingRow(Container):
    """Streaming placeholder shown while a reply is being generated.

    Shows a stage message (reading project, searching files, writing response)
    plus an animated progress bar so the assistant feels responsive. While a
    tool is executing, the stage can be pinned (``set_fixed_stage``) and each
    finished tool appends a ``✓`` line via ``add_done``.
    """

    STAGES = [
        "Reading project context",
        "Searching codebase",
        "Analyzing the request",
        "Writing response",
        "Finishing up",
    ]

    def __init__(self, fixed_stage: str | None = None, **kwargs):
        super().__init__(id="thinking-row", **kwargs)
        self.stage_label: Label | None = None
        self.progress_label: Label | None = None
        self.done_box: Vertical | None = None
        self._fixed_stage = fixed_stage
        self._stage_fixed = fixed_stage is not None
        self._pending_done: list = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="thinking-inner"):
            yield Label("✦", id="thinking-spin")
            initial = self._fixed_stage or ThinkingRow.STAGES[0]
            self.stage_label = Label(initial, id="thinking-stage")
            yield self.stage_label
        self.progress_label = Label("▰▱▱▱▱▱▱▱▱▱", id="thinking-progress")
        yield self.progress_label
        self.done_box = Vertical(id="thinking-done-box")
        yield self.done_box

    def on_mount(self) -> None:
        # done lines may have arrived before the row was attached; flush now
        self._flush_pending_done()

    def set_stage(self, index: int) -> None:
        if self._stage_fixed or self.stage_label is None:
            return
        stage = ThinkingRow.STAGES[index % len(ThinkingRow.STAGES)]
        self.stage_label.update(stage)

    def set_fixed_stage(self, text: str) -> None:
        """Pin the stage label (e.g. 'Running tools…') and stop cycling."""
        self._stage_fixed = True
        self._fixed_stage = text
        if self.stage_label is not None:
            self.stage_label.update(text)

    def add_done(self, text: str, warn: bool = False) -> None:
        """Append a completion line, e.g. ``✓ Searched glass`` (green) or
        ``✕ cargo build (cancelled)`` (amber when the user declined).

        Safe to call before the row's container is attached: pending lines
        are queued and flushed once ``done_box`` is mounted.
        """
        self._pending_done.append((text, warn))
        self._flush_pending_done()

    def _flush_pending_done(self) -> None:
        # Mounting children into an unattached container raises MountError,
        # so only flush once the done_box itself is attached.
        if self.done_box is None or not self.done_box.is_mounted:
            return
        for text, warn in self._pending_done:
            marker = "✕" if warn else "✓"
            cls = "thinking-done thinking-done-warn" if warn else "thinking-done"
            self.done_box.mount(Label(f"{marker} {text}", classes=cls))
        self._pending_done.clear()

    def set_progress(self, fraction: float) -> None:
        if self.progress_label is None:
            return
        filled = max(0, min(10, int(round(fraction * 10))))
        self.progress_label.update("▰" * filled + "▱" * (10 - filled))


class HeaderBar(Vertical):
    """Compact product hero: identity line + a single-line workspace status
    strip. Replaces the tall logo/tagline block and five wide info cards with
    two tight rows so the conversation starts higher on screen."""

    def __init__(self, project: dict, **kwargs):
        super().__init__(id="app-header", **kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        langs = " · ".join((self.project.get("languages") or [])[:3]) or "—"
        git_clean = self.project.get("git_clean", True)
        git = "✓ Clean" if git_clean else "✗ Modified"
        git_cls = "strip-git-clean" if git_clean else "strip-git-dirty"

        with Horizontal(id="hero-row"):
            yield Label(f"{theme.ICONS['bolt']} Capture Help", id="app-title")
            yield Label(
                f"{theme.ICONS['project']}  {self.project.get('name', 'project')}",
                id="project-name",
            )
            with Horizontal(id="workspace-strip"):
                yield Label(langs, id="strip-langs")
                yield Label(git, classes=f"strip-pill {git_cls}")
                yield Label(model_display_name(), classes="strip-pill strip-accent")


class StatusFooter(Horizontal):
    """Status bar: runtime identity (left) + live streaming stats (right)."""

    def __init__(self, project: dict | None = None, **kwargs):
        super().__init__(id="status-footer", **kwargs)
        self.project = project or {}
        self.model_label: Label | None = None
        self.provider_label: Label | None = None
        self.context_label: Label | None = None
        self.git_label: Label | None = None
        self.version_label: Label | None = None
        self.tokens_label: Label | None = None
        self.time_label: Label | None = None
        self.cost_label: Label | None = None
        self.state_label: Label | None = None

    def compose(self) -> ComposeResult:
        git_clean = self.project.get("git_clean", True)
        git_text = f"{theme.ICONS['git']} ✓ Clean" if git_clean else f"{theme.ICONS['git']} ✗ Modified"
        git_cls = "status-item git-clean" if git_clean else "status-item git-dirty"

        self.model_label = Label("", classes="status-item model")
        self.provider_label = Label("", classes="status-item")
        self.context_label = Label("", classes="status-item")
        self.git_label = Label(git_text, classes=git_cls)
        self.version_label = Label(f"v{__version__}", classes="status-item version")
        self.tokens_label = Label("", classes="status-item")
        self.time_label = Label("", classes="status-item")
        self.cost_label = Label("", classes="status-item cost")
        self.state_label = Label("", classes="status-item")

        yield self.model_label
        yield self.provider_label
        yield self.context_label
        yield self.git_label
        yield self.version_label
        yield Label("", classes="status-spacer")
        yield self.tokens_label
        yield self.time_label
        yield self.cost_label
        yield self.state_label

    def set_model(self, model: str) -> None:
        if not self.model_label:
            return
        name = model_display_name(model)
        is_local = (
            settings.default_provider == "ollama"
            or "gemma" in model.lower()
            or "localhost" in (settings.deepseek_base_url or "").lower()
            or "11434" in (settings.deepseek_base_url or "").lower()
        )
        tag = "LOCAL" if is_local else "CLOUD"
        badge = f"{tag} {name}"
        cls = "status-item model model-local" if is_local else "status-item model model-cloud"
        self.model_label.update(badge)
        self.model_label.set_classes(cls)

    def set_provider(self, provider: str | None = None) -> None:
        if self.provider_label:
            self.provider_label.update(provider or provider_display_name())

    def set_context(self, text: str) -> None:
        if self.context_label:
            self.context_label.update(f"Context {text}")

    def set_stats(self, stats) -> None:
        if not stats:
            return
        if self.tokens_label:
            self.tokens_label.update(f"{theme.ICONS['tokens']}  {stats.total_tokens:,} tok")
        if self.time_label:
            self.time_label.update(f"{theme.ICONS['time']}  {stats.duration_seconds:.1f}s")
        if self.cost_label:
            self.cost_label.update(f"{theme.ICONS['cost']}  ${stats.cost_usd:.5f}")

    def set_state(self, text: str, streaming: bool = False) -> None:
        if not self.state_label:
            return
        cls = "status-item state-streaming" if streaming else "status-item"
        self.state_label.update(text)
        self.state_label.set_classes(cls)

    def on_click(self, event) -> None:
        """Clicking the model label opens the model picker."""
        if event.widget is self.model_label:
            action = getattr(self.app, "action_open_model_picker", None)
            if action is not None:
                action()


def _sidebar_title(title: str, limit: int = 14) -> str:
    """Trim a session title to one short sidebar line."""
    text = re.sub(r"^https?://", "", title.strip())
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SidebarPanel(Vertical):
    """Left sidebar: recent chat sessions, files touched this session and
    the project's learned background memory."""

    def __init__(self, **kwargs):
        super().__init__(id="sidebar", **kwargs)
        self.recent_list: OptionList | None = None
        self.open_files: Vertical | None = None
        self.memory_list: Vertical | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="sidebar-brand"):
            yield Label("⚡", classes="sidebar-logo")
            yield Label("Capture Help", classes="sidebar-brand-title")
        with Horizontal(classes="sidebar-actions"):
            yield Button("＋ New", id="sidebar-new-chat", classes="sidebar-action")
            yield Button("⌕ Search", id="sidebar-search", classes="sidebar-action")
        with Vertical(classes="sidebar-section"):
            yield Label("CHATS", classes="sidebar-section-title")
            self.recent_list = OptionList(id="recent-chats")
            yield self.recent_list
        with Vertical(classes="sidebar-section"):
            yield Label("PROJECT FILES", classes="sidebar-section-title")
            self.open_files = Vertical(id="open-files")
            yield self.open_files
        with Vertical(classes="sidebar-section"):
            yield Label("LEARNED MEMORY", classes="sidebar-section-title")
            self.memory_list = Vertical(id="memory-list")
            yield self.memory_list

    def set_recent_chats(self, sessions: list, active_id: str | None = None) -> None:
        """Render the recent-chat list; the session matching ``active_id`` is
        marked with a cyan ``▌`` and a bold title so the current conversation
        stands out from the rest."""
        if not self.recent_list:
            return
        self.recent_list.clear_options()
        if not sessions:
            self.recent_list.add_option(Option("(no saved conversations)", id="none"))
            return
        for s in sessions:
            sid = str(s.get("id", ""))
            title = _sidebar_title(str(s.get("title", "Chat Session")))
            emoji = title_emoji(title)
            rel = relative_time(s.get("timestamp"))
            if sid == active_id:
                head = Text(f"▌ {emoji} {title}", style="bold #63c6e2")
            else:
                head = Text(f"  {emoji} {title}", style="")
            self.recent_list.add_option(
                Option(head + Text(f"\n  {rel}", style="dim"), id=f"session:{sid}")
            )

    def set_open_files(self, files: list) -> None:
        if not self.open_files:
            return
        self.open_files.remove_children()
        if not files:
            self.open_files.mount(Label("(none yet)", classes="sidebar-item"))
            return
        for f in files[:20]:
            self.open_files.mount(Label(f"▸ {f}", classes="sidebar-item"))

    def set_memories(self, memories: list) -> None:
        """Render learned project rules as ✓ lines under PROJECT MEMORY."""
        if not self.memory_list:
            return
        self.memory_list.remove_children()
        if not memories:
            self.memory_list.mount(Label("(none — /learn to teach me)", classes="sidebar-item"))
            return
        for m in memories[:8]:
            raw = (m.get("content") or "").strip()
            content = raw.splitlines()[0] if raw else ""
            text = f"✓ {content[:26]}" if content else "✓ (empty)"
            self.memory_list.mount(Label(text, classes="sidebar-item sidebar-memory"))


class DebugPanel(Vertical):
    """Collapsible debug/log panel, hidden by default (Ctrl+D to toggle)."""

    def __init__(self, **kwargs):
        super().__init__(id="debug-panel", **kwargs)
        self.rich_log: RichLog | None = None

    def compose(self) -> ComposeResult:
        with Collapsible(title="🐞 Debug & Logs", collapsed=True):
            self.rich_log = RichLog(id="debug-log", highlight=True, markup=True, wrap=True)
            yield self.rich_log

    def write(self, line: str) -> None:
        if self.rich_log is not None:
            self.rich_log.write(line)


# --------------------------------------------------------------------------- #
# Landing screen (empty state)
# --------------------------------------------------------------------------- #
EXAMPLE_PROMPTS = [
    "Explain code...",
    "Fix build errors...",
    "Generate docs...",
    "Refactor project...",
]

QUICK_ACTIONS = [
    ("explain", "⌘ Explain Code", "Explain the core architecture and key components of this project."),
    ("fix", "⌘ Fix Errors", "Find and fix build and runtime errors in this project."),
    ("search", "⌘ Search Project", "__SEARCH__"),
    ("review", "⌘ Review Changes", "Review my current uncommitted git changes and suggest improvements."),
    ("docs", "⌘ Generate Docs", "Generate thorough documentation for this project."),
    ("git", "⌘ Git Summary", "__DIFF__"),
]


class LandingPanel(Vertical):
    """The empty-state landing screen.

    Hero question, clickable example prompts, keyboard-navigable quick actions
    and a Today's-Workspace summary. It fades away once a conversation begins.
    """

    def __init__(self, **kwargs):
        super().__init__(id="landing", **kwargs)
        self.workspace: Vertical | None = None

    def compose(self) -> ComposeResult:
        yield Label("What would you like to build today?", id="landing-question")
        yield Label("Choose a starting point to get going", id="landing-sub")

        with Grid(id="example-row", classes="example-row"):
            for i, text in enumerate(EXAMPLE_PROMPTS):
                yield Button(text, id=f"chip-{i}", classes="chip")

        yield Button("▶  Ask Capture Help", id="qa-primary", classes="qa-btn qa-primary")
        yield Label("Quick Actions", classes="section-label")
        with Grid(id="qa-grid"):
            for key, label, _ in QUICK_ACTIONS:
                yield Button(label, id=f"qa-{key}", classes="qa-btn qa-secondary")

        with Vertical(classes="workspace-panel"):
            yield Label("Today's Workspace", classes="section-label")
            self.workspace_items = Vertical(id="workspace-items")
            yield self.workspace_items

    def set_workspace(self, summary: dict) -> None:
        """Render the Today's-Workspace summary as a two-column list."""
        if not self.workspace_items:
            return
        self.workspace_items.remove_children()
        branch = summary.get("branch") or "—"
        rows = [
            ("branch", "🌿  Branch", f"{branch}", "ws-good"),
            ("modified", "📄  Modified files",
             f"{summary.get('modified') or 0}", "ws-warn" if summary.get("modified") else "ws-value"),
            ("build", "🛠  Build",
             "✓ Passing" if summary.get("clean") else "✗ Checking",
             "ws-good" if summary.get("clean") else "ws-warn"),
            ("todos", "📝  TODOs", f"{summary.get('todos') or 0}", "ws-value"),
            ("deps", "📦  Dependencies", f"{summary.get('deps') or 0}", "ws-value"),
            ("tests", "🧪  Tests", f"{summary.get('tests') or 0}", "ws-value"),
        ]
        for key, left, right, cls in rows:
            row = Horizontal(classes="ws-row")
            self.workspace_items.mount(row)
            row.mount(Label(left, classes="ws-key"))
            row.mount(Label("", classes="status-spacer"))
            row.mount(Label(right, classes=f"ws-value {cls}"))
        # Last commit gets its own full-width line so the message can breathe.
        commit = summary.get("last_commit") or "No commits yet"
        row = Horizontal(classes="ws-row")
        self.workspace_items.mount(row)
        row.mount(Label("🕒  Last commit", classes="ws-key"))
        row.mount(Label("", classes="status-spacer"))
        row.mount(Label(commit[:60], classes="ws-value ws-commit"))

    def set_recent_chats(self, sessions: list) -> None:
        """Backward-compat no-op: recent conversations live in the sidebar now."""
        return


# --------------------------------------------------------------------------- #
# Slash-command discovery
# --------------------------------------------------------------------------- #
class SlashPopup(Vertical):
    """Autocomplete dropdown of slash commands shown above the prompt input.

    Typing ``/`` in the input pops this up (via ``show``). Filtering, arrow-key
    navigation and selection are driven by the app + ``ChatInput`` so that
    keyboard focus always stays in the input while the user narrows their query.
    """

    def __init__(self, commands: list, **kwargs):
        super().__init__(id="slash-popup", **kwargs)
        self.all_commands = commands
        self.option_list: OptionList | None = None

    def compose(self) -> ComposeResult:
        self.option_list = OptionList(id="slash-options")
        yield self.option_list

    def _matches(self, value: str) -> list:
        prefix = value.lstrip().lower()
        if not prefix:
            return list(self.all_commands)
        return [
            (cmd, desc)
            for cmd, desc in self.all_commands
            if cmd.startswith(prefix) or prefix in desc.lower()
        ]

    def show(self, value: str) -> int:
        """Repopulate with commands matching ``value`` and reveal if any match."""
        matches = self._matches(value)
        if self.option_list is None:
            return 0
        self.option_list.clear_options()
        for cmd, desc in matches:
            self.option_list.add_option(Option(f"{cmd}  —  {desc}", id=cmd))
        visible = bool(matches)
        self.styles.display = "block" if visible else "none"
        if matches:
            self.option_list.highlighted = 0
        return len(matches)

    def hide(self) -> None:
        self.styles.display = "none"

    def is_visible(self) -> bool:
        return self.styles.display != "none"

    def move(self, delta: int) -> None:
        if self.option_list is None:
            return
        count = len(self.option_list.options)
        if not count:
            return
        idx = self.option_list.highlighted
        idx = 0 if idx is None else idx
        self.option_list.highlighted = (idx + delta) % count

    def selected(self) -> str | None:
        """The id (command string) of the highlighted option, if any."""
        if self.option_list is None:
            return None
        opt = self.option_list.highlighted_option
        return getattr(opt, "id", None)


class ChatInput(TextArea):
    """Multiline prompt editor with slash suggestions and an explicit send key.

    Arrow keys move the popup highlight and Escape/Tab dismiss or fill it, but
    focus stays in the editor so the user can keep typing to narrow the list.
    Enter inserts a newline; Ctrl+Enter submits the prompt.
    """

    BINDINGS = [("ctrl+enter", "send_prompt", "Send")]

    @property
    def value(self) -> str:
        """Keep the former Input API for existing app flows and integrations."""
        return self.text

    @value.setter
    def value(self, value: str) -> None:
        self.load_text(value)
        lines = value.split("\n")
        self.cursor_location = (len(lines) - 1, len(lines[-1]))

    @property
    def cursor_position(self) -> int:
        line, column = self.cursor_location
        return sum(len(part) + 1 for part in self.text.split("\n")[:line]) + column

    @cursor_position.setter
    def cursor_position(self, position: int) -> None:
        before_cursor = self.text[:max(0, position)]
        line = before_cursor.count("\n")
        column = len(before_cursor.rsplit("\n", 1)[-1])
        self.cursor_location = (line, column)

    def action_send_prompt(self) -> None:
        self.app._submit_prompt(self.text)

    def action_paste(self) -> None:
        if self.read_only:
            return
        if self.app._paste_clipboard_image():
            return
        super().action_paste()

    def _popup(self) -> SlashPopup | None:
        try:
            return self.app.query_one("#slash-popup", SlashPopup)
        except Exception:
            return None

    def _accept_tab(self) -> None:
        popup = self._popup()
        if popup is None:
            return
        cmd = popup.selected()
        if cmd:
            self.value = cmd + " "
            self.cursor_position = len(self.value)
        popup.hide()
        self.focus()

    async def _on_key(self, event) -> None:
        popup = self._popup()
        if popup is not None and popup.is_visible():
            if event.key == "down":
                popup.move(1)
                event.stop()
                event.prevent_default()
                return
            if event.key == "up":
                popup.move(-1)
                event.stop()
                event.prevent_default()
                return
            if event.key == "escape":
                popup.hide()
                event.stop()
                event.prevent_default()
                return
            if event.key == "tab":
                self._accept_tab()
                event.stop()
                event.prevent_default()
                return
        await super()._on_key(event)
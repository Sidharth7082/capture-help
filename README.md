# <p align="center"><img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/catppuccin_banner.png" alt="capture-help header" width="100%"></p>

<h1 align="center">⚡ capture-help</h1>

<p align="center">
  <img src="assets/preview1.png" alt="capture-help terminal chat" width="48%">
  <img src="assets/preview2.png" alt="capture-help model selector" width="48%">
</p>

<p align="center">
  <b>A fast, modern, hyper-capable terminal AI developer assistant powered by DeepSeek & LLMs.</b><br>
  <i>Built with Python, Typer, Rich, and OpenAI SDK. Features full codebase indexing, interactive TUI, diff patching, system diagnostics, and security scanning.</i>
</p>

<p align="center">
  <a href="#-key-features"><img src="https://img.shields.io/badge/Features-40%2B%20Commands-8A2BE2?style=for-the-badge&logo=rocket" alt="Features"></a>
  <a href="#-installation"><img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"></a>
  <a href="https://github.com/Sidharth7082/capture-help/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License"></a>
  <a href="#-configuration"><img src="https://img.shields.io/badge/Provider-DeepSeek%20%7C%20Ollama-blue?style=for-the-badge&logo=openai" alt="Provider"></a>
</p>

---

## 📋 Table of Contents

- [✨ Highlights & Overview](#-highlights--overview)
- [🚀 Key Features](#-key-features)
- [📦 Installation](#-installation)
- [⚙️ Configuration & Environment](#-configuration--environment)
- [📖 Detailed Command Reference](#-detailed-command-reference)
  - [🧠 Core & Codebase Intelligence](#1-core--codebase-intelligence)
  - [💻 System & DevOps Diagnostics](#2-system--devops-diagnostics)
  - [🛡️ Security & Privacy](#3-security--privacy)
  - [⚡ Productivity & Utilities](#4-productivity--utilities)
- [💡 Workflow Examples](#-workflow-examples)
- [🎭 Personas & Customization](#-personas--customization)
- [⌨️ Shell Aliases](#-shell-aliases)
- [📜 License](#-license)

---

## ✨ Highlights & Overview

`capture-help` turns your local command line into an AI super-station. Designed for developers, DevOps engineers, and system admins, it offers context-aware codebase analysis, instant bug fixing with unified diff patches, terminal UI selectors, system health inspection, and deep security audits.

- **⚡ Blazing Fast**: Streaming markdown, rich syntax highlighting, and live cost calculation.
- **🧠 Codebase Conscious**: Auto-indexes repositories, reads `.gitignore`, builds AST graphs, and extracts accurate citations.
- **🛠️ Interactive Patching**: Preview diffs in rich colors and apply changes with automated `.bak` backups.
- **🔒 Privacy First**: Built-in secret masking and data redaction (`capture-help redact`).
- **🎛️ Multi-Provider**: Support for DeepSeek, Ollama, and customizable endpoints.

---

## 🚀 Key Features

```
               ┌──────────────────────────────────────────────┐
               │              capture-help CLI                │
               └──────────────────────┬───────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
┌───────▼───────┐             ┌───────▼───────┐             ┌───────▼───────┐
│ Code Base AI  │             │ System & TUI  │             │ Security/Audit│
│ • Ask / Index │             │ • Hermès / Arch│             │ • Scan Secrets│
│ • Fix / Patch │             │ • Disk/Memory │             │ • Redact Data │
│ • Review / Doc│             │ • Docker/TUI  │             │ • Guard Rules │
└───────────────┘             └───────────────┘             └───────────────┘
```

1. **Codebase Indexing & Question Answering (`capture-help ask`, `capture-help index`)**
   - Automatically parses files while respecting `.gitignore`.
   - Generates vector-like semantic indices to locate definitions, functions, and architecture logic.
2. **Interactive Diff Engine (`capture-help fix`)**
   - Renders visual `a/file` vs `b/file` color diffs before touching your disk.
   - Interactive confirmation prompt (`Apply this change? [y/N]`) with optional automatic backup creation.
3. **Hermès Autonomous Agent (`capture-help hermes`)**
   - Runs complex iterative tasks, auto-executes terminal commands with permission checks, inspects results, and fixes errors in a loop.
4. **Unix Pipe & Stdin Synergy**
   - Seamless integration with Unix pipelines:
     ```bash
     make 2>&1 | capture-help explain
     git diff | capture-help commit
     cat app.log | capture-help redact
     ```
5. **System Hardware & Security Audit (`capture-help neofetch`, `capture-help scan`, `capture-help arch`)**
   - Inspect GPU/CPU/Memory, firewall status (`ufw`/`nftables`), Docker instances, system security vulnerabilities, and hardcoded API tokens.

---

## 📦 Installation

### Option 1: Quick Local Install (Editable Mode)

```bash
git clone https://github.com/Sidharth7082/capture-help.git
cd capture-help
pip install -e .
```

### Option 2: Isolated Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## ⚙️ Configuration & Environment

Manage your settings interactively or through environment variables.

### Interactive Configuration

```bash
capture-help config
```

### Environment Variables (`.env`)

Create a `.env` file in your working directory or set environment variables in your shell:

```env
# DeepSeek API Settings
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Provider Selection (deepseek | ollama | custom)
DEFAULT_PROVIDER=deepseek

# System & Behavior Flags
CAPTURE_HELP_PERSONA=aggressive
CAPTURE_HELP_REDACT_SECRETS=true
```

---

## 📖 Detailed Command Reference

### 1. Core & Codebase Intelligence

| Command | Description | Example Usage |
| :--- | :--- | :--- |
| `ask` | Query the codebase with semantic file search & citations. | `capture-help ask "How is authentication handled?"` |
| `index` | Force rebuild or inspect the local codebase index. | `capture-help index --rebuild` |
| `chat` | Start interactive AI session with system context & history persistence. | `capture-help chat` |
| `explain` | Deep-dive explanation of source files or build error logs. | `make 2>&1 \| capture-help explain` |
| `fix` | Diagnose errors in code and apply interactive diff patches. | `capture-help fix src/main.rs` |
| `review` | Automated code review with project health summary dashboard. | `git diff \| capture-help review` |
| `refactor` | Clean up, modernize, or restructure target code files. | `capture-help refactor legacy.py` |
| `docs` | Auto-generate comprehensive docstrings & technical docs. | `capture-help docs api/router.go` |
| `test` | Generate framework-native unit tests (pytest, cargo test, etc.). | `capture-help test services/user.py` |
| `optimize` | Identify performance/memory bottlenecks with Big-O analysis. | `capture-help optimize algorithms.cpp` |
| `diagram` | Render ASCII / Mermaid diagrams of module architectures. | `capture-help diagram architecture` |
| `graph` | Display dependency structure & AST graph trees. | `capture-help graph` |

---

### 2. System & DevOps Diagnostics

| Command | Description | Example Usage |
| :--- | :--- | :--- |
| `hermes` | Launch the autonomous iterative subagent. | `capture-help hermes "Fix failing pytest suites"` |
| `arch` | System architecture inspection & OS diagnostic summary. | `capture-help arch` |
| `neofetch` | Sleek ASCII system statistics & environment info display. | `capture-help neofetch` |
| `disk` | Disk usage analysis & storage breakdown. | `capture-help disk` |
| `memory` | Real-time RAM & swap memory usage breakdown. | `capture-help memory` |
| `docker` | Container health, active containers, and image status. | `capture-help docker` |
| `gpu` | NVIDIA / VRAM hardware detection and load metrics. | `capture-help gpu` |
| `firewall` | Network rule evaluation & firewall health audit (`ufw`, `iptables`). | `capture-help firewall` |
| `tui` | Interactive TUI file picker & command selector console. | `capture-help tui` |
| `local` | Manage local Ollama models: `list`, `pull`, `use <model>`. | `capture-help local use qwen2.5-coder` |

---

### 3. Security & Privacy

| Command | Description | Example Usage |
| :--- | :--- | :--- |
| `scan` | Comprehensive security scan for hardcoded secrets & vulnerabilities. | `capture-help scan .` |
| `secrets` | Audit repository for leaked keys, passwords, and tokens. | `capture-help secrets` |
| `redact` | Redact sensitive passwords, IP addresses, and tokens from stdin/files. | `cat server.log \| capture-help redact` |
| `guard` | Validate project files against custom security rules. | `capture-help guard` |
| `audit` | Run full project security, performance & dependency audit. | `capture-help audit` |

---

### 4. Productivity & Utilities

| Command | Description | Example Usage |
| :--- | :--- | :--- |
| `commit` | Generate Conventional Commit messages from staged `git diff`. | `git diff --staged \| capture-help commit` |
| `summarize` | Condense git diffs, files, directories, or piped stdin into concise key takeaways. | `git diff HEAD~3 \| capture-help summarize` |
| `pr` | Draft Pull Request title & description based on commit logs. | `capture-help pr` |
| `changelog` | Automatically aggregate git history into `CHANGELOG.md`. | `capture-help changelog` |
| `history` | List and browse past chat sessions. | `capture-help history` |
| `resume` | Resume a specific prior conversation session by ID. | `capture-help resume 3` |
| `alias` | Install fast terminal shell shortcuts (`ai`, `aifix`, `aireview`). | `capture-help alias --install` |
| `doctor` | Self-diagnostic tool to check python env, dependencies, and API keys. | `capture-help doctor` |
| `clean` | Purge cached indices, temporary diffs, and session logs. | `capture-help clean` |
| `stats` | View total token consumption, total requests, and total cost metrics. | `capture-help stats` |
| `web` | Live web search (DuckDuckGo) with AI-grounded answers & cited sources. | `capture-help web "httpx vs requests"` |

---

## 💡 Workflow Examples

### 1. Codebase QA with Precise Citations
```bash
capture-help ask "Where is the configuration file loaded and parsed?"
```
*Output includes exact line numbers, file paths, and snippet context.*

---

### 2. Live Compiler Error Debugging
```bash
gcc -Wall main.c 2>&1 | capture-help explain
```
*Explains syntax or linker errors in plain English with solution recommendations.*

---

### 3. Interactive Code Patching
```bash
capture-help fix capture_help/cli.py
```
*Displays a syntax-highlighted diff:*
```diff
--- a/capture_help/cli.py
+++ b/capture_help/cli.py
@@ -42,3 +42,3 @@
- timeout = 10
+ timeout = 30
```
`Apply this change? [y/N]: y` -> *Files safely updated with a `.bak` backup file created.*

---

### 4. Automated Git Commits
```bash
git add .
capture-help commit
```
*Generates:*
`feat(cli): add interactive TUI selector and system diagnostic commands`

### 5. Instant Content Summaries
```bash
# Summarize your uncommitted work
capture-help summarize

# Summarize the last 3 commits of changes
capture-help summarize --ref HEAD~3

# Summarize a whole module
capture-help summarize capture_help/commands

# Summarize any piped output (logs, test runs, CI output)
make 2>&1 | capture-help summarize
```

### 6. Run Fully Offline with Local Ollama Models
Every command (including `summarize`) can run against local Ollama models instead of the cloud API — no API key needed:

```bash
# Activate any installed local model globally (auto-detects your Ollama server)
capture-help local use qwen2.5-coder:14b

# Or switch provider manually
capture-help config --provider ollama --model qwen2.5-coder:14b

# Force a single summarize command onto a local model
capture-help summarize --local --model gemma3:12b

# Switch back to cloud DeepSeek
capture-help config --provider deepseek --model deepseek-chat
```

`DEFAULT_PROVIDER=ollama` (or any model name with an Ollama tag like `gemma3:12b`, or a localhost base URL) automatically routes all commands to `http://localhost:11434/v1`.

---

## 🎭 Personas & Customization

`capture-help` ships with dynamic character personas you can switch between, plus a full CLI to create your own. A persona is just a system-prompt overlay — **you fully control its behavior, tone, and rules**; capture-help does not inject any content restrictions into personas you create.

Built-in templates (start with `capture-help persona create <name> --template <t>`):

- **aggressive**: Highly concise, brutal efficiency, zero fluff, direct code focus.
- **senior**: Senior Architect perspective emphasizing design patterns, edge cases, and scalability.

Manage personas from the CLI:
```bash
capture-help persona list                          # show installed + active
capture-help persona templates                     # list built-in templates
capture-help persona create mybot --template aggressive   # start from a template
capture-help persona create mybot                  # fully interactive, free-form system prompt
capture-help persona activate mybot                # apply to all sessions
capture-help persona show mybot                    # view the full definition
capture-help persona edit mybot                    # tweak the system prompt in $EDITOR
capture-help persona export mybot --out mybot.json # share / back up
capture-help persona import mybot.json
capture-help persona delete mybot
capture-help persona reset                         # back to default assistant
```

Set a persona for a single chat session:
```bash
capture-help chat --persona aggressive
```

Within chat, use `/persona` to switch live (`/persona gehrman`, `/persona 1`, `/persona reset`).

### Longer, Uninterrupted Answers

capture-help no longer truncates your conversation to a tiny fixed window. The context is configurable:

```bash
CAPTURE_HELP_CONTEXT_MESSAGES=0 capture-help chat   # unlimited context (whole conversation)
CAPTURE_HELP_CONTEXT_MESSAGES=50 capture-help chat  # or a larger fixed window (default 30)
```

---

## ⌨️ Shell Aliases

Speed up your terminal workflow by installing built-in shell aliases:

```bash
capture-help alias --install
```

This adds the following shortcuts to your `~/.bashrc` / `~/.zshrc`:

| Shortcut | Mapped Command |
| :--- | :--- |
| `ai` | `capture-help chat` |
| `aiask` | `capture-help ask` |
| `aifix` | `capture-help fix` |
| `aireview` | `capture-help review` |
| `aidoc` | `capture-help docs` |
| `aicommit` | `capture-help commit` |

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

<p align="center">Made with ❤️ by the Capture Team</p>

"""MyGlass frosted-glass color palette shared by the Textual chat UI.

True glassmorphism (blur / transparency) is not possible in a terminal, so we
emulate it with layered near-black surfaces, subtle cyan accents, soft rounded
borders and a careful use of whitespace.
"""

# Base surfaces (dark layered glass)
BASE = "#0d1017"          # deepest background
SURFACE_1 = "#12161f"     # main panels
SURFACE_2 = "#171c28"     # cards / inputs / bubbles
SURFACE_3 = "#1d2432"     # raised elements / hover
EDGE = "#232b3c"          # faint borders
EDGE_SOFT = "#1b2230"     # even fainter separators

# Text hierarchy
TEXT = "#e8edf4"          # primary text (near white)
TEXT_MUTED = "#8f9aa9"    # secondary text
TEXT_DIM = "#5d6878"      # tertiary / metadata

# Accents
ACCENT = "#63c6e2"        # subtle MyGlass cyan
ACCENT_DIM = "#3a7d92"    # darker cyan for borders on dark
ACCENT_GLOW = "#9adcf0"   # bright hover / focus
VIOLET = "#a78bfa"        # AI brand accent

# Semantic
SUCCESS = "#4ed98c"       # green
WARNING = "#e5b95c"       # amber
ERROR = "#f2556f"         # red
INFO = "#6aa9f0"          # blue

# Bubble backgrounds
USER_BG = "#1c3140"       # user bubble glass (cyan-tinted)
ASSISTANT_BG = "#161b26"  # assistant bubble glass
TOOL_BG = "#181d29"       # tool execution card
THINK_BG = "#151a24"      # thinking / streaming card

ICONS = {
    "bolt": "⚡",
    "chat": "💬",
    "model": "🧠",
    "time": "⏱",
    "tokens": "▦",
    "cost": "¢",
    "project": "▤",
    "git": "⎇",
    "language": "λ",
    "wrench": "🛠",
    "bug": "🐞",
    "search": "⌕",
    "clear": "⌫",
    "debug": "⌘",
    "user": "◆",
    "robot": "✦",
}

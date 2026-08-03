import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

DEFAULT_IGNORE_DIRS = {
    ".git", "venv", ".venv", "node_modules", "build", "dist",
    ".cache", "target", "__pycache__", ".eggs", "*.egg-info", ".idea", ".vscode"
}

def load_ignore_patterns(root_path: Path) -> List[str]:
    """Load ignore rules from .capturehelpignore in project root or user config."""
    patterns = list(DEFAULT_IGNORE_DIRS)
    
    # Check project root .capturehelpignore
    proj_ignore = root_path / ".capturehelpignore"
    if proj_ignore.exists():
        try:
            with open(proj_ignore, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line.rstrip("/"))
        except Exception:
            pass

    # Check global config ignore
    global_ignore = Path.home() / ".config" / "capture-help" / "ignore"
    if global_ignore.exists():
        try:
            with open(global_ignore, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line.rstrip("/"))
        except Exception:
            pass

    return list(set(patterns))

def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Recursively search upward for git root or build configuration root."""
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists() or (parent / "CMakeLists.txt").exists() or (parent / "Cargo.toml").exists():
            return parent
    return curr

def fingerprint_project(root_path: Optional[Path] = None) -> Dict[str, Any]:
    """Analyze repository to detect languages, build systems, frameworks, and git status."""
    root = find_project_root(root_path)
    ignore_patterns = load_ignore_patterns(root)

    build_systems = []
    if (root / "CMakeLists.txt").exists():
        build_systems.append("CMake")
    if (root / "Cargo.toml").exists():
        build_systems.append("Cargo")
    if (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "requirements.txt").exists():
        build_systems.append("Python (pip/uv)")
    if (root / "package.json").exists():
        build_systems.append("Node.js (npm/yarn)")
    if (root / "Makefile").exists() or (root / "makefile").exists():
        build_systems.append("Makefile")

    frameworks = []
    for f in root.glob("*.qml"):
        frameworks.append("Qt / QML")
        break
    if not frameworks:
        for f in root.rglob("*.qml"):
            if not any(ign in str(f) for ign in ignore_patterns):
                frameworks.append("Qt / QML")
                break

    lang_extensions = {
        ".cpp": "C++", ".hpp": "C++", ".c": "C", ".h": "C/C++",
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React JSX", ".tsx": "React TSX", ".rs": "Rust",
        ".go": "Go", ".java": "Java", ".qml": "Qt QML",
        ".lua": "Lua", ".sh": "Shell", ".css": "CSS", ".html": "HTML"
    }

    lang_counts: Dict[str, int] = {}
    total_files = 0

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in lang_extensions:
                lang = lang_extensions[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
                total_files += 1

    top_langs = sorted(lang_counts.items(), key=lambda x: x[1], reverse=True)[:4]
    lang_list = [l[0] for l in top_langs]

    git_clean = True
    if (root / ".git").exists():
        try:
            import subprocess
            res = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True)
            if res.stdout.strip():
                git_clean = False
        except Exception:
            pass

    return {
        "root": root,
        "name": root.name,
        "languages": lang_list,
        "build_systems": build_systems,
        "frameworks": frameworks,
        "git_clean": git_clean,
        "total_files": total_files,
    }

def search_project_context(query: str, root_path: Optional[Path] = None, top_k: int = 5) -> Tuple[List[Tuple[Path, str, float]], int]:
    """Scan and rank relevant project code snippets based on query keywords. Returns (matches, scanned_files_count)."""
    root = find_project_root(root_path)
    ignore_patterns = load_ignore_patterns(root)
    valid_exts = {".cpp", ".hpp", ".c", ".h", ".py", ".js", ".ts", ".rs", ".go", ".qml", ".lua", ".sh", ".toml", ".json", ".txt", ".md"}

    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return [], 0

    file_scores: List[Tuple[Path, str, float]] = []
    scanned_files_count = 0

    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignore_patterns and not any(ign in d for ign in ignore_patterns)]
        for f in files:
            p = Path(r) / f
            if p.suffix.lower() not in valid_exts:
                continue

            scanned_files_count += 1
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fo:
                    text = fo.read(100_000)

                filename_score = sum(3.0 for word in query_words if word in p.name.lower())
                content_words = re.findall(r"\w+", text.lower())
                if not content_words:
                    continue

                matched_count = sum(1 for word in content_words if word in query_words)
                score = filename_score + (matched_count / (len(content_words) ** 0.5 + 1))

                if score > 0.1:
                    file_scores.append((p, text, score))
            except Exception:
                pass

    file_scores.sort(key=lambda x: x[2], reverse=True)
    return file_scores[:top_k], scanned_files_count

"""
Code analysis tools — plain Python functions registered with AutoGen agents.

Unlike the Ollama version (where Python calls these before the LLM),
here the LLM itself decides when to call these via AutoGen's agentic loop.
AutoGen executes each tool call and feeds the result back to the model.
"""
from datetime import datetime
from pathlib import Path

_MAX_FILE_CHARS = 6_000
_MAX_DIR_ENTRIES = 60


def read_file(path: str) -> str:
    """Read a source file and return its content (capped at 6000 characters)."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Error: file not found: {path}"
        if not p.is_file():
            return f"Error: not a regular file: {path}"
        text = p.read_text(encoding="utf-8", errors="replace")
        total = len(text)
        if total > _MAX_FILE_CHARS:
            text = text[:_MAX_FILE_CHARS]
            text += f"\n\n... [truncated — {total} chars total, showing first {_MAX_FILE_CHARS}]"
        return text
    except PermissionError:
        return f"Error: permission denied reading {path}"
    except Exception as exc:
        return f"Error: {exc}"


def list_directory(path: str) -> str:
    """List files and subdirectories in a directory, skipping hidden files and build artifacts."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Error: directory not found: {path}"
        if not p.is_dir():
            return f"Error: not a directory: {path}"

        lines = [f"Contents of {p}:"]
        count = 0
        for item in sorted(p.iterdir()):
            if item.name.startswith(".") or item.name in ("__pycache__", "node_modules", "venv", ".git"):
                continue
            if count >= _MAX_DIR_ENTRIES:
                lines.append(f"  ... (more entries omitted, limit {_MAX_DIR_ENTRIES})")
                break
            if item.is_dir():
                lines.append(f"  [DIR]  {item.name}/")
            else:
                size = item.stat().st_size
                lines.append(f"  [FILE] {item.name}  ({size} bytes)")
            count += 1

        if count == 0:
            return f"Directory is empty: {path}"
        return "\n".join(lines)
    except PermissionError:
        return f"Error: permission denied listing {path}"
    except Exception as exc:
        return f"Error: {exc}"


def get_file_stats(path: str) -> str:
    """Return metadata about a file: size in bytes, line count, and last modification time."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Error: not found: {path}"
        s = p.stat()
        mod = datetime.fromtimestamp(s.st_mtime).isoformat(timespec="seconds")
        line_count = -1
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                line_count = text.count("\n") + 1
            except Exception:
                pass
        return (
            f"Path:      {path}\n"
            f"Size:      {s.st_size} bytes\n"
            f"Lines:     {line_count}\n"
            f"Modified:  {mod}\n"
            f"Extension: {p.suffix}"
        )
    except Exception as exc:
        return f"Error: {exc}"

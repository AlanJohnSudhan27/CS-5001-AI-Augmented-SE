"""
Code analysis tools — plain Python functions called directly by agents.

With Ollama/llama3.2:3b the LLM does not call tools autonomously. Instead,
each agent calls these functions in Python to gather context before
sending the accumulated data to the LLM in a single prompt.

No Anthropic tool definitions needed here.
"""
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List

_MAX_FILE_CHARS = 6_000    # chars returned per file read
_MAX_DIR_ENTRIES = 60      # max entries listed per directory


def _resolve(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def read_file(path: str) -> str:
    """Read a source file and return its content (capped at _MAX_FILE_CHARS)."""
    try:
        p = _resolve(path)
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
    """List files and subdirectories in a directory."""
    try:
        p = _resolve(path)
        if not p.exists():
            return f"Error: directory not found: {path}"
        if not p.is_dir():
            return f"Error: not a directory: {path}"

        lines: List[str] = [f"Contents of {path}:"]
        count = 0
        for item in sorted(p.iterdir()):
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            if count >= _MAX_DIR_ENTRIES:
                lines.append(f"  ... (more entries omitted, limit {_MAX_DIR_ENTRIES})")
                break
            if item.is_dir():
                lines.append(f"  [DIR]  {item.name}/")
            else:
                try:
                    size = item.stat().st_size
                    lines.append(f"  [FILE] {item.name}  ({size} bytes)")
                except OSError:
                    lines.append(f"  [FILE] {item.name}")
            count += 1

        if count == 0:
            return f"Directory is empty: {path}"
        return "\n".join(lines)
    except PermissionError:
        return f"Error: permission denied listing {path}"
    except Exception as exc:
        return f"Error: {exc}"


def get_file_stats(path: str) -> str:
    """Return metadata about a file: size, line count, modification time."""
    try:
        p = _resolve(path)
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

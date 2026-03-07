from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def ensure_repo_path(repo: str) -> Path:
    path = Path(repo).resolve()
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"Invalid repo path: {repo}")
    return path


def ensure_ollama_available() -> None:
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, text=True, check=True)
    except Exception:
        raise SystemExit("Ollama CLI not found. Install Ollama and ensure `ollama` is on PATH.")


def ensure_model_available(model: str) -> None:
    try:
        out = subprocess.check_output(["ollama", "list"], text=True)
    except Exception:
        raise SystemExit("Unable to run `ollama list`. Ensure Ollama is installed and running.")

    names: set[str] = set()
    for line in (out or "").splitlines():
        s = line.strip()
        if not s or s.lower().startswith("name "):
            continue
        name = s.split()[0]
        if name:
            names.add(name)

    if model not in names:
        raise SystemExit(f"Ollama model '{model}' not found locally. Run: ollama pull {model}")


def clamp(text: str, max_chars: int = 10000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED]"


def parse_json_object(text: str) -> dict[str, Any]:
    s = (text or "").strip()
    if not s:
        raise ValueError("Empty JSON response")

    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON output must be an object")
    return parsed

"""
AnalyzerAgent — Stage 1 of the pipeline.

Gathers all file context in Python (list_directory, get_file_stats, read_file),
then sends everything to the LLM in one prompt with format="json".

Output: AnalysisResult
"""
import json
from pathlib import Path
from typing import Callable, List, Optional

from agents.base import BaseAgent
from models.schemas import AnalysisResult
from tools.code_tools import get_file_stats, list_directory, read_file

# Source file extensions to read
_SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".swift"}
# Max files to read (keeps prompt size manageable)
_MAX_FILES = 10
# Max chars per file sent to the LLM
_MAX_CHARS_PER_FILE = 4_000


class AnalyzerAgent(BaseAgent):
    name = "Analyzer"
    system_prompt = """\
You are the Analyzer — the first agent in a code review pipeline.

You will be given the full source code of one or more files along with their
file stats. Your job is to produce a precise structural map.

Respond with ONLY a valid JSON object matching this exact schema:

{
  "files_analyzed": ["list of file paths"],
  "functions": ["module.func_name(params) -> return_type", ...],
  "classes": ["ClassName: one-sentence description", ...],
  "imports": ["import statement or module name", ...],
  "complexity_notes": ["function X has N branches", "class Y is large (N lines)", ...],
  "loc_total": <integer total lines across all files>,
  "language": "Python",
  "summary": "One sentence describing what this codebase does."
}

List ALL functions and classes. Complexity notes should flag deeply nested logic,
functions longer than 50 lines, or functions with more than 5 parameters.
"""

    def run(
        self,
        target_path: str,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> AnalysisResult:
        p = Path(target_path).expanduser().resolve()
        kind = "directory" if p.is_dir() else "file"

        if emit:
            emit(self.name, f"Scanning {kind}: {p}")

        # ── 1. Discover files ──────────────────────────────────
        source_files = _discover_files(p, emit)

        # ── 2. Gather context in Python ────────────────────────
        file_blocks: List[str] = []
        loc_total = 0

        for f in source_files:
            stats = get_file_stats(str(f))
            content = read_file(str(f))
            if emit:
                emit(self.name, f"[tool] read_file({f.name})")

            # Count lines from stats output
            for line in stats.splitlines():
                if line.startswith("Lines:"):
                    try:
                        loc_total += int(line.split(":")[1].strip())
                    except ValueError:
                        pass

            # Truncate per-file content for LLM
            if len(content) > _MAX_CHARS_PER_FILE:
                content = content[:_MAX_CHARS_PER_FILE] + f"\n... [truncated]"

            file_blocks.append(
                f"=== FILE: {f} ===\n"
                f"--- stats ---\n{stats}\n"
                f"--- source ---\n{content}\n"
            )

        if emit:
            emit(self.name, f"Read {len(source_files)} file(s) — {loc_total} total lines")

        # ── 3. Build prompt and call LLM ───────────────────────
        code_context = "\n".join(file_blocks) if file_blocks else "(no source files found)"

        prompt = (
            f"Analyze the following code at path: {p}\n\n"
            f"{code_context}\n\n"
            "Return the JSON structural map."
        )

        raw_text = self.chat([{"role": "user", "content": prompt}], emit)
        raw = self._parse_json(raw_text)

        # Fill in loc_total from our own count if LLM left it empty/wrong
        if not raw.get("loc_total"):
            raw["loc_total"] = loc_total
        if not raw.get("files_analyzed"):
            raw["files_analyzed"] = [str(f) for f in source_files]

        if emit:
            emit(self.name, f"Analysis complete — {raw.get('loc_total', '?')} total lines")

        return AnalysisResult.from_dict(raw)


def _discover_files(p: Path, emit) -> List[Path]:
    """Return source files under p, up to _MAX_FILES."""
    if p.is_file():
        return [p]

    # List top-level directory for the log
    if emit:
        emit("Analyzer", f"[tool] list_directory({p.name}/)")

    files: List[Path] = []
    for item in sorted(p.rglob("*")):
        if item.is_file() and item.suffix in _SOURCE_EXTS:
            parts = item.parts
            if any(s in parts for s in ("__pycache__", ".git", "node_modules", "venv", ".venv")):
                continue
            files.append(item)
        if len(files) >= _MAX_FILES:
            break

    return files

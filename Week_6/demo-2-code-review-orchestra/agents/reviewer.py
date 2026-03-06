"""
ReviewerAgent — Stage 2 of the pipeline.

Re-reads the files identified by the Analyzer (Python tool calls), then sends
code + analysis to the LLM in one prompt to identify issues.

Output: ReviewResult
"""
import json
from pathlib import Path
from typing import Callable, List, Optional

from agents.base import BaseAgent
from models.schemas import AnalysisResult, ReviewResult
from tools.code_tools import read_file

_MAX_CHARS_PER_FILE = 4_000


class ReviewerAgent(BaseAgent):
    name = "Reviewer"
    system_prompt = """\
You are the Reviewer — the second agent in a code review pipeline.

You will be given source code and a structural analysis from the Analyzer.
Your job is to identify concrete problems:
  - Bugs: logic errors, off-by-one errors, incorrect assumptions
  - Security: injection risks, hardcoded credentials, unsafe deserialization
  - Code smells: duplicated logic, God objects, long methods, magic numbers
  - Style: inconsistent naming, missing error handling, poor readability

Respond with ONLY a valid JSON object matching this exact schema:

{
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "bug|security|smell|style",
      "description": "Clear description of the problem",
      "location": "filename.py:line_number or function_name",
      "evidence": "Exact code snippet or specific reason"
    }
  ],
  "overall_risk": "critical|high|medium|low",
  "files_reviewed": ["list of file paths reviewed"],
  "summary": "One sentence overall assessment."
}

Sort issues from most severe to least. If the code is clean, return few or no issues.
"""

    def run(
        self,
        target_path: str,
        analysis: AnalysisResult,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> ReviewResult:
        if emit:
            emit(self.name, f"Reviewing {len(analysis.files_analyzed)} file(s)")

        # ── 1. Re-read files in Python ─────────────────────────
        file_blocks: List[str] = []
        for path_str in analysis.files_analyzed:
            content = read_file(path_str)
            if emit:
                emit(self.name, f"[tool] read_file({Path(path_str).name})")
            if len(content) > _MAX_CHARS_PER_FILE:
                content = content[:_MAX_CHARS_PER_FILE] + "\n... [truncated]"
            file_blocks.append(f"=== {path_str} ===\n{content}")

        code_context = "\n\n".join(file_blocks) if file_blocks else "(no files)"
        analysis_json = json.dumps(analysis.to_dict(), indent=2)

        # ── 2. Build prompt and call LLM ───────────────────────
        prompt = (
            f"Target path: {target_path}\n\n"
            f"=== STRUCTURAL ANALYSIS ===\n{analysis_json}\n\n"
            f"=== SOURCE CODE ===\n{code_context}\n\n"
            "Identify all issues and return the JSON review."
        )

        raw_text = self.chat([{"role": "user", "content": prompt}], emit)
        raw = self._parse_json(raw_text)

        if not raw.get("files_reviewed"):
            raw["files_reviewed"] = analysis.files_analyzed

        issue_count = len(raw.get("issues", []))
        if emit:
            emit(self.name, f"Found {issue_count} issue(s) — risk: {raw.get('overall_risk', '?')}")

        return ReviewResult.from_dict(raw)

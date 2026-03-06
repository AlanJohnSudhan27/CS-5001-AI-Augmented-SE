"""
SuggesterAgent — Stage 3 of the pipeline.

Re-reads source files in Python, then sends code + analysis + review to the
LLM in one prompt to produce concrete before/after improvement suggestions.

Output: SuggestionResult
"""
import json
from pathlib import Path
from typing import Callable, List, Optional

from agents.base import BaseAgent
from models.schemas import AnalysisResult, ReviewResult, SuggestionResult
from tools.code_tools import read_file

_MAX_CHARS_PER_FILE = 4_000


class SuggesterAgent(BaseAgent):
    name = "Suggester"
    system_prompt = """\
You are the Suggester — the third agent in a code review pipeline.

You will be given source code, a structural analysis, and a list of issues.
Your job is to propose concrete, actionable improvements with before/after
code snippets. Focus on the highest-impact changes first.

Respond with ONLY a valid JSON object matching this exact schema:

{
  "improvements": [
    {
      "priority": 1,
      "title": "Short descriptive title",
      "rationale": "Why this improvement matters",
      "before": "current code snippet (keep to 5-10 lines)",
      "after": "improved code snippet (keep to 5-10 lines)",
      "addresses_issue": "Which issue from the review this fixes"
    }
  ],
  "quick_wins": [
    "One-liner fix: rename variable x to user_count in utils.py:42"
  ],
  "summary": "One sentence summarizing the improvement opportunities."
}

Priority 1 = highest impact. Provide at least 2 improvements if issues exist.
Keep before/after snippets concise — 5 to 10 lines each.
"""

    def run(
        self,
        target_path: str,
        analysis: AnalysisResult,
        review: ReviewResult,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> SuggestionResult:
        if emit:
            emit(self.name, f"Generating improvements for {len(review.issues)} issue(s)")

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
        review_json = json.dumps(review.to_dict(), indent=2)

        # ── 2. Build prompt and call LLM ───────────────────────
        prompt = (
            f"Target path: {target_path}\n\n"
            f"=== STRUCTURAL ANALYSIS ===\n{analysis_json}\n\n"
            f"=== REVIEW ISSUES ===\n{review_json}\n\n"
            f"=== SOURCE CODE ===\n{code_context}\n\n"
            "Propose concrete improvements and return the JSON."
        )

        raw_text = self.chat([{"role": "user", "content": prompt}], emit)
        raw = self._parse_json(raw_text)

        imp_count = len(raw.get("improvements", []))
        if emit:
            emit(self.name, f"Proposed {imp_count} improvement(s)")

        return SuggestionResult.from_dict(raw)

"""
SummarizerAgent — Stage 4 (final) of the pipeline.

Synthesizes the three upstream agent outputs into an executive summary
with an overall quality score (0-100). No file reading needed.

Output: FinalReport
"""
import json
from datetime import datetime, timezone
from typing import Callable, Optional

from agents.base import BaseAgent
from models.schemas import (
    AnalysisResult,
    FinalReport,
    ReviewResult,
    SuggestionResult,
)


class SummarizerAgent(BaseAgent):
    name = "Summarizer"
    system_prompt = """\
You are the Summarizer — the final agent in a code review pipeline.

You will be given the complete outputs of three upstream agents:
  1. Analyzer  — structural map of the code
  2. Reviewer  — list of issues with severity ratings
  3. Suggester — ranked improvements with before/after snippets

Synthesize these into a concise executive report.

Score the code quality from 0 to 100:
  90-100: Excellent, production-ready
  75-89:  Good, minor improvements needed
  60-74:  Average, notable issues present
  40-59:  Poor, significant refactoring needed
  0-39:   Critical problems, major rework required

Deduct points: critical/high issues (-15 each), medium issues (-5 each),
high complexity (-10), missing error handling (-5).

Respond with ONLY a valid JSON object matching this exact schema:

{
  "executive_summary": "2-3 sentences for a non-technical audience",
  "overall_score": <integer 0-100>,
  "critical_findings": [
    "Most important finding, stated plainly"
  ],
  "top_improvements": [
    "Single most impactful thing to fix"
  ]
}

Keep critical_findings and top_improvements to 2-5 items each.
"""

    def run(
        self,
        analysis: AnalysisResult,
        review: ReviewResult,
        suggestions: SuggestionResult,
        target_path: str,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> FinalReport:
        if emit:
            emit(self.name, "Synthesizing final report")

        analysis_json = json.dumps(analysis.to_dict(), indent=2)
        review_json = json.dumps(review.to_dict(), indent=2)
        suggestions_json = json.dumps(suggestions.to_dict(), indent=2)

        prompt = (
            f"Target: {target_path}\n\n"
            f"=== ANALYZER OUTPUT ===\n{analysis_json}\n\n"
            f"=== REVIEWER OUTPUT ===\n{review_json}\n\n"
            f"=== SUGGESTER OUTPUT ===\n{suggestions_json}\n\n"
            "Synthesize these into the executive report JSON."
        )

        raw_text = self.chat([{"role": "user", "content": prompt}], emit)
        raw = self._parse_json(raw_text)

        score = raw.get("overall_score", 50)
        if emit:
            emit(self.name, f"Final score: {score}/100")

        return FinalReport(
            executive_summary=raw.get("executive_summary", ""),
            overall_score=int(score),
            critical_findings=raw.get("critical_findings", []),
            top_improvements=raw.get("top_improvements", []),
            analysis=analysis,
            review=review,
            suggestions=suggestions,
            target_path=target_path,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

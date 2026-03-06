"""
Orchestrator — manages the 4-agent code review pipeline.

Sequential mode (default):
  Analyzer → Reviewer → Suggester → Summarizer

Parallel mode (--parallel flag):
  Analyzer → [Reviewer ∥ Suggester] → Summarizer
  (Reviewer and Suggester run concurrently via asyncio.gather;
   each gets the AnalysisResult; Suggester uses a placeholder review)

The emit callback is called with (agent_name, message) for every log event.
The web UI routes.py wraps this in an async context and forwards events via SSE.
"""
import asyncio
import json
from pathlib import Path
from typing import Callable, Optional

import config
from agents.analyzer import AnalyzerAgent
from agents.reviewer import ReviewerAgent
from agents.suggester import SuggesterAgent
from agents.summarizer import SummarizerAgent
from models.schemas import (
    AnalysisResult,
    FinalReport,
    ReviewResult,
    SuggestionResult,
)


class Orchestrator:
    """Runs the code review pipeline and persists the final report."""

    def run(
        self,
        target_path: str,
        parallel: bool = False,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> FinalReport:
        """
        Run the pipeline synchronously.

        Args:
            target_path: file or directory to review
            parallel: if True, run Reviewer and Suggester concurrently
            emit: optional callback(agent_name, message)

        Returns:
            FinalReport with all pipeline results.
        """
        p = str(Path(target_path).expanduser().resolve())

        # Stage 1 — Analyzer (always sequential)
        _emit(emit, "Orchestrator", f"Starting pipeline — target: {p}")
        _emit(emit, "Orchestrator", f"Mode: {'parallel' if parallel else 'sequential'}")

        analysis = AnalyzerAgent().run(p, emit)

        # Stages 2 & 3 — Reviewer + Suggester
        if parallel:
            review, suggestions = asyncio.run(
                _run_reviewer_suggester_parallel(p, analysis, emit)
            )
        else:
            review = ReviewerAgent().run(p, analysis, emit)
            suggestions = SuggesterAgent().run(p, analysis, review, emit)

        # Stage 4 — Summarizer
        report = SummarizerAgent().run(analysis, review, suggestions, p, emit)

        # Persist
        _save_report(report)
        _emit(emit, "Orchestrator", "Pipeline complete. Report saved.")

        return report

    async def run_async(
        self,
        target_path: str,
        parallel: bool = False,
        emit: Optional[Callable[[str, str], None]] = None,
    ) -> FinalReport:
        """
        Async variant for the web API — runs the pipeline in a thread pool
        so it doesn't block the event loop.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.run, target_path, parallel, emit
        )


# ── Internal helpers ───────────────────────────────────────────

async def _run_reviewer_suggester_parallel(
    target_path: str,
    analysis: AnalysisResult,
    emit: Optional[Callable[[str, str], None]],
) -> tuple[ReviewResult, SuggestionResult]:
    """
    Run Reviewer and Suggester concurrently.

    The Suggester gets the analysis but a placeholder ReviewResult so it
    can run in parallel. The Summarizer later integrates both results.
    """
    loop = asyncio.get_event_loop()

    placeholder_review = ReviewResult(
        issues=[],
        overall_risk="medium",
        files_reviewed=analysis.files_analyzed,
        summary="Review running in parallel — placeholder.",
    )

    review_fut = loop.run_in_executor(
        None,
        ReviewerAgent().run,
        target_path,
        analysis,
        emit,
    )
    suggest_fut = loop.run_in_executor(
        None,
        SuggesterAgent().run,
        target_path,
        analysis,
        placeholder_review,
        emit,
    )

    review, suggestions = await asyncio.gather(review_fut, suggest_fut)
    return review, suggestions


def _emit(
    emit: Optional[Callable[[str, str], None]],
    agent: str,
    message: str,
) -> None:
    if emit:
        emit(agent, message)


def _save_report(report: FinalReport) -> None:
    """Persist the report to .last_report.json."""
    try:
        config.REPORT_FILE.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass  # non-fatal — CLI `last` command simply won't work


def load_last_report() -> Optional[FinalReport]:
    """Load the most recently saved report, or None if none exists."""
    try:
        if not config.REPORT_FILE.exists():
            return None
        data = json.loads(config.REPORT_FILE.read_text(encoding="utf-8"))
        return FinalReport.from_dict(data)
    except Exception:
        return None

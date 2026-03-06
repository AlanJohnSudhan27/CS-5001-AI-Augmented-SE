"""
Data models for Code Review Orchestra.
All @dataclass — zero external dependencies.

Pipeline flow:
  AnalyzerAgent  → AnalysisResult
  ReviewerAgent  → ReviewResult
  SuggesterAgent → SuggestionResult
  SummarizerAgent → FinalReport
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ── AnalyzerAgent output ───────────────────────────────────────

@dataclass
class AnalysisResult:
    """Structural map of the code produced by AnalyzerAgent."""
    files_analyzed: List[str]
    functions: List[str]       # "module.func_name(args) -> return"
    classes: List[str]         # "ClassName: brief description"
    imports: List[str]         # top-level imports
    complexity_notes: List[str]  # "function X has N branches"
    loc_total: int
    language: str              # "Python", "JavaScript", etc.
    summary: str               # one-sentence structural overview

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        return cls(
            files_analyzed=d.get("files_analyzed", []),
            functions=d.get("functions", []),
            classes=d.get("classes", []),
            imports=d.get("imports", []),
            complexity_notes=d.get("complexity_notes", []),
            loc_total=int(d.get("loc_total", 0)),
            language=d.get("language", "Unknown"),
            summary=d.get("summary", ""),
        )


# ── ReviewerAgent output ───────────────────────────────────────

@dataclass
class Issue:
    """A single identified code issue."""
    severity: str    # "critical" | "high" | "medium" | "low"
    category: str    # "bug" | "security" | "smell" | "style"
    description: str
    location: str    # "file.py:line or function name"
    evidence: str    # quoted code snippet or specific reason

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        return cls(
            severity=d.get("severity", "medium"),
            category=d.get("category", "smell"),
            description=d.get("description", ""),
            location=d.get("location", ""),
            evidence=d.get("evidence", ""),
        )


@dataclass
class ReviewResult:
    """Severity-ranked issues produced by ReviewerAgent."""
    issues: List[Issue]
    overall_risk: str    # "critical" | "high" | "medium" | "low"
    files_reviewed: List[str]
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewResult":
        return cls(
            issues=[Issue.from_dict(i) for i in d.get("issues", [])],
            overall_risk=d.get("overall_risk", "medium"),
            files_reviewed=d.get("files_reviewed", []),
            summary=d.get("summary", ""),
        )


# ── SuggesterAgent output ──────────────────────────────────────

@dataclass
class Improvement:
    """A single actionable improvement with before/after snippets."""
    priority: int      # 1 = highest
    title: str
    rationale: str
    before: str        # current code snippet
    after: str         # improved code snippet
    addresses_issue: str  # links to an issue description

    @classmethod
    def from_dict(cls, d: dict) -> "Improvement":
        return cls(
            priority=int(d.get("priority", 1)),
            title=d.get("title", ""),
            rationale=d.get("rationale", ""),
            before=d.get("before", ""),
            after=d.get("after", ""),
            addresses_issue=d.get("addresses_issue", ""),
        )


@dataclass
class SuggestionResult:
    """Ranked improvements produced by SuggesterAgent."""
    improvements: List[Improvement]
    quick_wins: List[str]  # one-liners for trivial fixes
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SuggestionResult":
        return cls(
            improvements=[Improvement.from_dict(i) for i in d.get("improvements", [])],
            quick_wins=d.get("quick_wins", []),
            summary=d.get("summary", ""),
        )


# ── SummarizerAgent output ─────────────────────────────────────

@dataclass
class FinalReport:
    """Executive summary of the full pipeline, produced by SummarizerAgent."""
    executive_summary: str
    overall_score: int        # 0-100 code quality score
    critical_findings: List[str]
    top_improvements: List[str]
    analysis: AnalysisResult
    review: ReviewResult
    suggestions: SuggestionResult
    target_path: str
    generated_at: str         # ISO timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FinalReport":
        return cls(
            executive_summary=d.get("executive_summary", ""),
            overall_score=int(d.get("overall_score", 50)),
            critical_findings=d.get("critical_findings", []),
            top_improvements=d.get("top_improvements", []),
            analysis=AnalysisResult.from_dict(d.get("analysis", {})),
            review=ReviewResult.from_dict(d.get("review", {})),
            suggestions=SuggestionResult.from_dict(d.get("suggestions", {})),
            target_path=d.get("target_path", ""),
            generated_at=d.get("generated_at", ""),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, List


@dataclass(frozen=True)
class AgentConfig:
    repo: str
    model: str
    host: str
    temperature: float
    verbose: bool


@dataclass(frozen=True)
class RunResult:
    ok: bool
    details: str
    summary: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Multi-agent data types
# ---------------------------------------------------------------------------


@dataclass
class ReviewerResult:
    """Output from the Reviewer Agent (Tool Use Pattern).

    Contains static analysis results, LLM deep analysis, and raw diff data.
    All content is grounded in actual git diff — no fabrication.
    """

    issues: List
    category: Any          # ChangeCategory | None
    risk: Any              # RiskAssessment | None
    llm_analysis: str
    diff_result: Any       # DiffResult | None
    files_summary: List[dict] = field(default_factory=list)


@dataclass
class PlannerResult:
    """Structured plan from the Planner Agent (Planning Pattern artifact).

    Produced BEFORE any drafting begins. Specifies what to write,
    what evidence to cite, and why the action is warranted.
    """

    action: str            # "create_issue" | "create_pr" | "no_action"
    artifact_type: str     # "issue" | "pr"
    sections: List[str]
    key_points: List[str]
    evidence: List[str]
    rationale: str
    raw_plan: str


@dataclass
class IssueDraft:
    """GitHub Issue draft produced by the Writer Agent."""

    title: str
    problem_description: str
    evidence: str
    acceptance_criteria: List[str]
    risk_level: str
    labels: List[str] = field(default_factory=list)
    raw: str = ""


@dataclass
class PRDraft:
    """GitHub Pull Request draft produced by the Writer Agent."""

    title: str
    summary: str
    files_affected: List[str]
    behavior_change: str
    test_plan: str
    risk_level: str
    base_branch: str = "main"
    raw: str = ""


@dataclass
class ReflectionResult:
    """Reflection artifact from the Critic Agent (Reflection Pattern).

    Checks the draft for: unsupported claims, missing evidence,
    missing tests, and policy violations. Always produced before
    the Gatekeeper shows the draft to the user.
    """

    passed: bool
    unsupported_claims: List[str]
    missing_evidence: List[str]
    missing_tests: List[str]
    policy_violations: List[str]
    suggestions: List[str]
    overall_quality: str   # "good" | "needs_improvement" | "poor"
    raw: str = ""


@dataclass
class GatekeeperPackage:
    """Package assembled by the Gatekeeper Agent for human approval.

    Nothing is created on GitHub until approved is set to True
    by an explicit human action.
    """

    draft_type: str        # "issue" | "pr"
    draft: Any             # IssueDraft | PRDraft
    reflection: ReflectionResult
    reviewer_summary: dict
    approved: Optional[bool] = None
    rejection_reason: str = ""

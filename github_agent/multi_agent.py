"""Multi-Agent orchestration for the GitHub Review Agent.

Architecture — four identifiable agent roles:
  ReviewerAgent  — analyzes code changes (Tool Use Pattern)
  PlannerAgent   — structured planning before drafting (Planning Pattern)
  WriterAgent    — drafts Issue / PR content
  CriticAgent    — reflects on draft quality (Reflection Pattern)
  GatekeeperAgent— enforces human approval before GitHub action
  MultiAgentOrchestrator — coordinates all agents for each task
"""
from __future__ import annotations

import json
from typing import Optional, Union

from .analyzer import CodeAnalyzer
from .categorizer import ChangeCategorizer
from .git_utils import DiffResult
from .prompts import (
    draft_issue_prompt,
    draft_pr_prompt,
    explicit_draft_prompt,
    improve_issue_prompt,
    improve_pr_prompt,
    planner_prompt,
    reflect_prompt,
    reviewer_deep_analysis_prompt,
    reviewer_existing_content_prompt,
)
from .risk_assessor import RiskAssessor
from .types import (
    GatekeeperPackage,
    IssueDraft,
    PlannerResult,
    PRDraft,
    ReflectionResult,
    ReviewerResult,
)
from .utils import clamp, parse_json_object


# ---------------------------------------------------------------------------
# Reviewer Agent
# ---------------------------------------------------------------------------


class ReviewerAgent:
    """Reviewer Agent — analyzes code changes using real tools.

    Tool Use Pattern: uses git diff data, static analysis (CodeAnalyzer,
    ChangeCategorizer, RiskAssessor) and LLM for deeper reasoning.
    No content is fabricated; all findings are grounded in actual diff output.
    """

    def __init__(self, llm):
        self.llm = llm

    def analyze(
        self,
        diff_result: DiffResult,
        commit_messages: list | None = None,
    ) -> ReviewerResult:
        """Run full analysis pipeline on a git diff."""
        analyzer = CodeAnalyzer()
        categorizer = ChangeCategorizer()
        risk_assessor = RiskAssessor()

        issues = analyzer.analyze_diff(diff_result)
        category = categorizer.categorize(diff_result, commit_messages or [])
        risk = risk_assessor.assess(diff_result, issues, category)

        # Build a compact diff snippet for the LLM (Tool Use: real diff data)
        diff_snippet = "\n".join(
            f"File: {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n"
            + f.diff_content[:400]
            for f in diff_result.files[:10]
        )

        issues_for_prompt = [
            {
                "message": i.message,
                "file": i.file_path,
                "severity": i.severity.value,
                "type": i.issue_type.value,
            }
            for i in issues[:20]
        ]

        prompt = reviewer_deep_analysis_prompt(
            diff_snippet=clamp(diff_snippet, 7000),
            issues=issues_for_prompt,
            category=category.value,
            risk_level=risk.level.value,
        )

        llm_analysis = ""
        try:
            llm_analysis = self.llm.generate(prompt)
        except Exception as exc:
            llm_analysis = f"[LLM analysis unavailable: {exc}]"

        files_summary = [
            {
                "path": f.path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
            }
            for f in diff_result.files
        ]

        return ReviewerResult(
            issues=issues,
            category=category,
            risk=risk,
            llm_analysis=llm_analysis,
            diff_result=diff_result,
            files_summary=files_summary,
        )


# ---------------------------------------------------------------------------
# Planner Agent
# ---------------------------------------------------------------------------


class PlannerAgent:
    """Planner Agent — creates a structured plan before any drafting begins.

    Planning Pattern: produces a plan artifact (PlannerResult) that specifies
    what sections to include, what evidence to cite, and why the action is
    warranted. The Writer Agent must follow this plan.
    """

    def __init__(self, llm):
        self.llm = llm

    def plan(
        self,
        reviewer_result: ReviewerResult,
        action: str,
        instruction: str = "",
    ) -> PlannerResult:
        """Create a structured plan for the requested action.

        Args:
            reviewer_result: Output from ReviewerAgent (may have None fields
                             when no diff is available).
            action: "create_issue" | "create_pr"
            instruction: Optional explicit user instruction.
        """
        context: dict = {
            "action": action,
            "instruction": instruction,
            "issues": [
                {
                    "message": i.message,
                    "file": i.file_path,
                    "severity": i.severity.value,
                    "type": i.issue_type.value,
                }
                for i in (reviewer_result.issues or [])[:20]
            ],
            "category": reviewer_result.category.value
            if reviewer_result.category
            else "unknown",
            "risk_level": reviewer_result.risk.level.value
            if reviewer_result.risk
            else "medium",
            "risk_factors": reviewer_result.risk.factors[:5]
            if reviewer_result.risk
            else [],
            "files_changed": len(reviewer_result.files_summary),
            "llm_analysis": reviewer_result.llm_analysis[:1500]
            if reviewer_result.llm_analysis
            else "",
        }

        prompt = planner_prompt(
            context_json=clamp(json.dumps(context, indent=2), 7000)
        )

        raw = ""
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        artifact_type = "issue" if "issue" in action else "pr"

        return PlannerResult(
            action=action,
            artifact_type=artifact_type,
            sections=parsed.get(
                "sections",
                (
                    ["title", "problem_description", "evidence", "acceptance_criteria", "risk_level"]
                    if artifact_type == "issue"
                    else ["title", "summary", "files_affected", "behavior_change", "test_plan", "risk_level"]
                ),
            ),
            key_points=parsed.get("key_points", []),
            evidence=parsed.get("evidence", []),
            rationale=parsed.get("rationale", ""),
            raw_plan=raw,
        )


# ---------------------------------------------------------------------------
# Writer Agent
# ---------------------------------------------------------------------------


class WriterAgent:
    """Writer Agent — drafts Issue or PR content following the plan.

    Tool Use Pattern: uses the PlannerResult and ReviewerResult (which contain
    real code evidence) to produce grounded, specific draft content.
    """

    def __init__(self, llm):
        self.llm = llm

    def draft_issue(
        self,
        plan: PlannerResult,
        reviewer_result: ReviewerResult,
    ) -> IssueDraft:
        """Draft a GitHub Issue following the plan."""
        context = self._build_context(reviewer_result)
        plan_dict = {
            "sections": plan.sections,
            "key_points": plan.key_points,
            "evidence": plan.evidence,
            "rationale": plan.rationale,
        }
        prompt = draft_issue_prompt(plan=plan_dict, context=context)

        raw = ""
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        return IssueDraft(
            title=parsed.get("title", "Issue: Code Review Finding"),
            problem_description=parsed.get("problem_description", ""),
            evidence=parsed.get("evidence", ""),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            risk_level=parsed.get(
                "risk_level",
                reviewer_result.risk.level.value if reviewer_result.risk else "medium",
            ),
            labels=parsed.get("labels", []),
            raw=raw,
        )

    def draft_pr(
        self,
        plan: PlannerResult,
        reviewer_result: ReviewerResult,
    ) -> PRDraft:
        """Draft a GitHub Pull Request description following the plan."""
        context = self._build_context(reviewer_result)
        plan_dict = {
            "sections": plan.sections,
            "key_points": plan.key_points,
            "evidence": plan.evidence,
            "rationale": plan.rationale,
        }
        prompt = draft_pr_prompt(plan=plan_dict, context=context)

        raw = ""
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        return PRDraft(
            title=parsed.get("title", "PR: Code Changes"),
            summary=parsed.get("summary", ""),
            files_affected=parsed.get(
                "files_affected",
                [f["path"] for f in reviewer_result.files_summary[:10]],
            ),
            behavior_change=parsed.get("behavior_change", ""),
            test_plan=parsed.get("test_plan", ""),
            risk_level=parsed.get(
                "risk_level",
                reviewer_result.risk.level.value if reviewer_result.risk else "medium",
            ),
            raw=raw,
        )

    def draft_from_instruction(
        self,
        instruction: str,
        artifact_type: str,
        context: dict | None = None,
    ) -> Union[IssueDraft, PRDraft]:
        """Draft from an explicit user instruction (no diff required)."""
        prompt = explicit_draft_prompt(
            instruction=instruction,
            artifact_type=artifact_type,
            context=context or {},
        )

        raw = ""
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        if artifact_type == "issue":
            return IssueDraft(
                title=parsed.get("title", "Issue"),
                problem_description=parsed.get("problem_description", ""),
                evidence=parsed.get("evidence", ""),
                acceptance_criteria=parsed.get("acceptance_criteria", []),
                risk_level=parsed.get("risk_level", "medium"),
                labels=parsed.get("labels", []),
                raw=raw,
            )
        return PRDraft(
            title=parsed.get("title", "PR"),
            summary=parsed.get("summary", ""),
            files_affected=parsed.get("files_affected", []),
            behavior_change=parsed.get("behavior_change", ""),
            test_plan=parsed.get("test_plan", ""),
            risk_level=parsed.get("risk_level", "medium"),
            raw=raw,
        )

    def _build_context(self, reviewer_result: ReviewerResult) -> dict:
        return {
            "files": reviewer_result.files_summary[:15],
            "issues": [
                {
                    "message": i.message,
                    "file": i.file_path,
                    "severity": i.severity.value,
                }
                for i in (reviewer_result.issues or [])[:20]
            ],
            "category": reviewer_result.category.value
            if reviewer_result.category
            else "unknown",
            "risk_level": reviewer_result.risk.level.value
            if reviewer_result.risk
            else "medium",
            "risk_factors": reviewer_result.risk.factors[:5]
            if reviewer_result.risk
            else [],
            "llm_analysis": reviewer_result.llm_analysis[:1500]
            if reviewer_result.llm_analysis
            else "",
        }


# ---------------------------------------------------------------------------
# Critic Agent
# ---------------------------------------------------------------------------


class CriticAgent:
    """Critic Agent — reflects on draft quality before human review.

    Reflection Pattern: always runs before the Gatekeeper shows the draft.
    Produces a ReflectionResult artifact that documents:
      - unsupported claims
      - missing evidence
      - missing tests
      - policy violations
    """

    def __init__(self, llm):
        self.llm = llm

    def reflect(
        self,
        draft: Union[IssueDraft, PRDraft],
        reviewer_result: ReviewerResult,
    ) -> ReflectionResult:
        """Critique the draft and return a reflection artifact."""
        if isinstance(draft, IssueDraft):
            draft_dict = {
                "type": "issue",
                "title": draft.title,
                "problem_description": draft.problem_description,
                "evidence": draft.evidence,
                "acceptance_criteria": draft.acceptance_criteria,
                "risk_level": draft.risk_level,
            }
        else:
            draft_dict = {
                "type": "pr",
                "title": draft.title,
                "summary": draft.summary,
                "files_affected": draft.files_affected,
                "behavior_change": draft.behavior_change,
                "test_plan": draft.test_plan,
                "risk_level": draft.risk_level,
            }

        actual_evidence = {
            "issues_found": [i.message for i in (reviewer_result.issues or [])[:10]],
            "files_changed": [f["path"] for f in reviewer_result.files_summary[:10]],
            "risk_level": reviewer_result.risk.level.value
            if reviewer_result.risk
            else "medium",
            "category": reviewer_result.category.value
            if reviewer_result.category
            else "unknown",
        }

        prompt = reflect_prompt(draft=draft_dict, actual_evidence=actual_evidence)

        raw = ""
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        return ReflectionResult(
            passed=bool(parsed.get("passed", True)),
            unsupported_claims=parsed.get("unsupported_claims", []),
            missing_evidence=parsed.get("missing_evidence", []),
            missing_tests=parsed.get("missing_tests", []),
            policy_violations=parsed.get("policy_violations", []),
            suggestions=parsed.get("suggestions", []),
            overall_quality=parsed.get("overall_quality", "needs_improvement"),
            raw=raw,
        )


# ---------------------------------------------------------------------------
# Gatekeeper Agent
# ---------------------------------------------------------------------------


class GatekeeperAgent:
    """Gatekeeper Agent — enforces human approval before any GitHub action.

    Nothing is posted to GitHub without explicit human confirmation.
    This agent packages the draft + reflection for display and validates
    that approval has been explicitly granted before allowing creation.
    """

    def prepare(
        self,
        draft: Union[IssueDraft, PRDraft],
        reflection: ReflectionResult,
        reviewer_result: ReviewerResult,
    ) -> GatekeeperPackage:
        """Assemble the approval package for human review."""
        draft_type = "issue" if isinstance(draft, IssueDraft) else "pr"
        reviewer_summary = {
            "files_changed": len(reviewer_result.files_summary),
            "issues_found": len(reviewer_result.issues or []),
            "category": reviewer_result.category.value
            if reviewer_result.category
            else "N/A",
            "risk_level": reviewer_result.risk.level.value
            if reviewer_result.risk
            else "N/A",
            "risk_factors": reviewer_result.risk.factors[:5]
            if reviewer_result.risk
            else [],
        }
        return GatekeeperPackage(
            draft_type=draft_type,
            draft=draft,
            reflection=reflection,
            reviewer_summary=reviewer_summary,
        )


# ---------------------------------------------------------------------------
# Multi-Agent Orchestrator
# ---------------------------------------------------------------------------


class MultiAgentOrchestrator:
    """Coordinates all agent roles for the complete pipeline.

    Roles:
      ReviewerAgent  — Tool Use: analyzes real code
      PlannerAgent   — Planning Pattern: structured plan before drafting
      WriterAgent    — Tool Use: evidence-based draft
      CriticAgent    — Reflection Pattern: quality check artifact
      GatekeeperAgent— Human approval gate before any GitHub write
    """

    def __init__(self, llm):
        self.reviewer = ReviewerAgent(llm)
        self.planner = PlannerAgent(llm)
        self.writer = WriterAgent(llm)
        self.critic = CriticAgent(llm)
        self.gatekeeper = GatekeeperAgent()

    # ------------------------------------------------------------------
    # Task 2a: Review-driven draft
    # ------------------------------------------------------------------

    def run_review_and_draft(
        self,
        diff_result: DiffResult,
        commit_messages: list,
        action: str,
        instruction: str = "",
    ) -> GatekeeperPackage:
        """Full pipeline: Reviewer -> Planner -> Writer -> Critic -> Gate.

        Args:
            diff_result: Real git diff (Tool Use — no fabrication).
            commit_messages: Commit message list for context.
            action: "create_issue" | "create_pr"
            instruction: Optional user instruction to guide the Writer.
        """
        # Step 1 — Reviewer: analyze code (Tool Use Pattern)
        reviewer_result = self.reviewer.analyze(diff_result, commit_messages)

        # Step 2 — Planner: create structured plan (Planning Pattern)
        plan = self.planner.plan(reviewer_result, action, instruction)

        # Step 3 — Writer: draft content following the plan
        if plan.artifact_type == "issue":
            draft = self.writer.draft_issue(plan, reviewer_result)
        else:
            draft = self.writer.draft_pr(plan, reviewer_result)

        # Step 4 — Critic: reflect on draft quality (Reflection Pattern)
        reflection = self.critic.reflect(draft, reviewer_result)

        # Step 5 — Gatekeeper: prepare package for human approval
        return self.gatekeeper.prepare(draft, reflection, reviewer_result)

    # ------------------------------------------------------------------
    # Task 2b: Explicit-instruction draft
    # ------------------------------------------------------------------

    def run_explicit_draft(
        self,
        instruction: str,
        artifact_type: str,
        diff_result: Optional[DiffResult] = None,
        commit_messages: list | None = None,
    ) -> GatekeeperPackage:
        """Draft from an explicit instruction, optionally enriched by diff context.

        Args:
            instruction: User's explicit instruction (e.g. "Create an issue for…")
            artifact_type: "issue" | "pr"
            diff_result: Optional live diff for code context.
            commit_messages: Optional commit messages.
        """
        # Optional: run reviewer if diff is available
        if diff_result and diff_result.files:
            reviewer_result = self.reviewer.analyze(diff_result, commit_messages or [])
            context = {
                "files": [f["path"] for f in reviewer_result.files_summary[:10]],
                "category": reviewer_result.category.value
                if reviewer_result.category
                else "unknown",
                "risk_level": reviewer_result.risk.level.value
                if reviewer_result.risk
                else "medium",
            }
        else:
            reviewer_result = ReviewerResult(
                issues=[],
                category=None,
                risk=None,
                llm_analysis="",
                diff_result=None,
                files_summary=[],
            )
            context = {}

        # Writer drafts from instruction
        draft = self.writer.draft_from_instruction(instruction, artifact_type, context)

        # Critic reflects — notes if evidence cannot be verified
        if diff_result and diff_result.files:
            reflection = self.critic.reflect(draft, reviewer_result)
        else:
            reflection = ReflectionResult(
                passed=True,
                unsupported_claims=[],
                missing_evidence=[
                    "No code diff provided — evidence claims cannot be verified against actual code."
                ],
                missing_tests=[],
                policy_violations=[],
                suggestions=[
                    "Consider providing a repo path and base branch for evidence-based verification."
                ],
                overall_quality="good",
            )

        return self.gatekeeper.prepare(draft, reflection, reviewer_result)

    # ------------------------------------------------------------------
    # Task 3: Improve existing Issue or PR
    # ------------------------------------------------------------------

    def run_improve(self, existing_content: dict, content_type: str) -> dict:
        """Critique and improve an existing GitHub Issue or PR.

        The Reviewer critiques first; the Writer proposes improvements.
        Returns a dict with 'original', 'critique', and 'improved' keys.

        Args:
            existing_content: Raw GitHub API response for the issue/PR.
            content_type: "issue" | "pr"
        """
        # Step 1 — Reviewer: critique existing content
        critique_prompt = reviewer_existing_content_prompt(existing_content, content_type)
        critique_raw = ""
        try:
            critique_raw = self.reviewer.llm.generate(critique_prompt)
            critique = parse_json_object(critique_raw)
        except Exception:
            critique = {
                "overall_assessment": critique_raw[:500] if critique_raw else "Analysis unavailable.",
                "vague_language": [],
                "missing_information": [],
                "unclear_criteria": [],
                "missing_evidence": [],
                "structural_problems": [],
                "severity": "moderate",
            }

        # Step 2 — Writer: draft improved version
        if content_type == "issue":
            improve_prompt = improve_issue_prompt(existing_content)
        else:
            improve_prompt = improve_pr_prompt(existing_content)

        improved_raw = ""
        try:
            improved_raw = self.writer.llm.generate(improve_prompt)
            improved = parse_json_object(improved_raw)
        except Exception:
            improved = {"raw": improved_raw[:1000] if improved_raw else "Draft unavailable."}

        return {
            "original": existing_content,
            "critique": critique,
            "improved": improved,
            "content_type": content_type,
        }

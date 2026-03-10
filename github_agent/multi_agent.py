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

import datetime as dt
import json
import os
from pathlib import Path
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

ISSUE_REQUIRED_SECTIONS = ["problem_description", "evidence", "acceptance_criteria", "risk_level"]
PR_REQUIRED_SECTIONS = ["summary", "files_affected", "behavior_change", "test_plan", "risk_level"]
ALLOWED_QUALITY = {"good", "needs_improvement", "poor"}


def _is_fast_mode() -> bool:
    return True


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
        fast = _is_fast_mode()
        max_files = 2 if fast else 10
        max_diff_chars = 90 if fast else 400
        max_prompt_issues = 5 if fast else 20
        llm_clamp = 1200 if fast else 7000

        diff_snippet = "\n".join(
            f"File: {f.path} ({f.status}, +{f.additions}/-{f.deletions})\n"
            + f.diff_content[:max_diff_chars]
            for f in diff_result.files[:max_files]
        )

        issues_for_prompt = [
            {
                "message": i.message,
                "file": i.file_path,
                "severity": i.severity.value,
                "type": i.issue_type.value,
            }
            for i in issues[:max_prompt_issues]
        ]

        llm_analysis = ""
        prompt = reviewer_deep_analysis_prompt(
            diff_snippet=clamp(diff_snippet, llm_clamp),
            issues=issues_for_prompt,
            category=category.value,
            risk_level=risk.level.value,
        )
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
        tool_evidence = self._build_tool_evidence(diff_result, issues, commit_messages or [])

        return ReviewerResult(
            issues=issues,
            category=category,
            risk=risk,
            llm_analysis=llm_analysis,
            diff_result=diff_result,
            files_summary=files_summary,
            tool_evidence=tool_evidence,
        )

    def _build_tool_evidence(self, diff_result: DiffResult, issues: list, commit_messages: list[str]) -> dict:
        file_entries = []
        file_limit = 8 if _is_fast_mode() else 25
        for idx, file_change in enumerate(diff_result.files[:file_limit], start=1):
            file_entries.append(
                {
                    "id": f"file-{idx}",
                    "path": file_change.path,
                    "status": file_change.status,
                    "additions": file_change.additions,
                    "deletions": file_change.deletions,
                }
            )

        issue_entries = []
        issue_limit = 10 if _is_fast_mode() else 50
        for idx, issue in enumerate((issues or [])[:issue_limit], start=1):
            issue_entries.append(
                {
                    "id": f"issue-{idx}",
                    "file": issue.file_path,
                    "line": issue.line_number,
                    "severity": issue.severity.value,
                    "type": issue.issue_type.value,
                    "message": issue.message[:120],
                }
            )

        commit_entries = []
        commit_limit = 8 if _is_fast_mode() else 20
        for idx, message in enumerate((commit_messages or [])[:commit_limit], start=1):
            clean = str(message).strip()
            if not clean:
                continue
            commit_entries.append({"id": f"commit-{idx}", "message": clean})

        return {
            "source": "tool_use_pipeline",
            "files": file_entries,
            "issues": issue_entries,
            "commits": commit_entries,
        }


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
                    "message": i.message[:120],
                    "file": i.file_path,
                    "severity": i.severity.value,
                    "type": i.issue_type.value,
                }
                for i in (reviewer_result.issues or [])[:6]
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
            "files": [f.get("path") for f in reviewer_result.files_summary[:8] if f.get("path")],
            "tool_evidence_ids": {
                "files": [f.get("id") for f in reviewer_result.tool_evidence.get("files", [])[:8]],
                "issues": [i.get("id") for i in reviewer_result.tool_evidence.get("issues", [])[:8]],
            },
        }

        raw = ""
        parsed: dict = {}
        prompt = planner_prompt(
            context_json=clamp(json.dumps(context, indent=2), 1800 if _is_fast_mode() else 7000)
        )
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = {}

        artifact_type = "issue" if "issue" in action else "pr"
        normalized = self._normalize_plan(parsed, reviewer_result, artifact_type)

        return PlannerResult(
            action=action,
            artifact_type=artifact_type,
            sections=normalized["sections"],
            key_points=normalized["key_points"],
            evidence=normalized["evidence"],
            rationale=normalized["rationale"],
            raw_plan=raw,
        )

    @staticmethod
    def _coerce_list_of_str(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if str(v).strip()]

    def _normalize_plan(
        self,
        parsed: dict,
        reviewer_result: ReviewerResult,
        artifact_type: str,
    ) -> dict[str, list[str] | str]:
        required_sections = ISSUE_REQUIRED_SECTIONS if artifact_type == "issue" else PR_REQUIRED_SECTIONS
        sections = self._coerce_list_of_str(parsed.get("sections"))
        for section in required_sections:
            if section not in sections:
                sections.append(section)
        if "title" not in sections:
            sections.insert(0, "title")

        key_points = self._coerce_list_of_str(parsed.get("key_points"))
        if not key_points:
            key_points = [
                f"Category: {reviewer_result.category.value if reviewer_result.category else 'unknown'}",
                f"Risk level: {reviewer_result.risk.level.value if reviewer_result.risk else 'medium'}",
                f"Issue count: {len(reviewer_result.issues or [])}",
            ]

        evidence = self._coerce_list_of_str(parsed.get("evidence"))
        if not evidence:
            evidence = [
                f"file:{f.get('path')}"
                for f in (reviewer_result.files_summary or [])[:8]
                if f.get("path")
            ]
            evidence.extend(
                [
                    f"issue:{i.file_path}:{i.line_number or 'n/a'}:{i.message}"
                    for i in (reviewer_result.issues or [])[:8]
                ]
            )
        evidence = evidence[:20]

        rationale = str(parsed.get("rationale") or "").strip()
        if not rationale:
            rationale = (
                "Action is warranted based on observed risk, concrete issue findings, "
                "and changed files in the analyzed diff."
            )

        return {
            "sections": sections,
            "key_points": key_points[:15],
            "evidence": evidence,
            "rationale": rationale,
        }


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
            evidence=self._coerce_issue_evidence(
                parsed.get("evidence"),
                reviewer_result.files_summary,
                reviewer_result.issues,
            ),
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
            files_affected=self._coerce_files_affected(
                parsed.get("files_affected"),
                reviewer_result.files_summary,
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
        fast = _is_fast_mode()
        allowed_file_limit = 4 if fast else 20
        allowed_issue_limit = 6 if fast else 20
        return {
            "files": reviewer_result.files_summary[:allowed_file_limit],
            "issues": [
                {
                    "message": i.message[:120],
                    "file": i.file_path,
                    "severity": i.severity.value,
                }
                for i in (reviewer_result.issues or [])[:allowed_issue_limit]
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
            "tool_evidence_ids": {
                "files": [f.get("id") for f in reviewer_result.tool_evidence.get("files", [])[:allowed_file_limit]],
                "issues": [i.get("id") for i in reviewer_result.tool_evidence.get("issues", [])[:allowed_issue_limit]],
            },
            "evidence_ledger": {
                "allowed_files": [f["path"] for f in reviewer_result.files_summary[:allowed_file_limit] if f.get("path")],
                "allowed_issue_refs": [
                    {
                        "file": i.file_path,
                        "line": i.line_number,
                        "message": i.message[:120],
                    }
                    for i in (reviewer_result.issues or [])[:allowed_issue_limit]
                ],
            },
        }

    @staticmethod
    def _coerce_files_affected(value: object, files_summary: list[dict]) -> list[str]:
        allowed = {f.get("path") for f in files_summary if f.get("path")}
        if isinstance(value, list):
            filtered = [str(v).strip() for v in value if str(v).strip() in allowed]
            if filtered:
                return filtered[:10]
        return [f.get("path") for f in files_summary[:10] if f.get("path")]

    @staticmethod
    def _coerce_issue_evidence(value: object, files_summary: list[dict], issues: list) -> str:
        text = str(value or "").strip()
        allowed_files = [f.get("path") for f in files_summary if f.get("path")]
        referenced = [path for path in allowed_files if path in text]
        if referenced:
            return text

        file_refs = ", ".join(allowed_files[:5]) if allowed_files else "none"
        issue_refs = []
        for issue in (issues or [])[:5]:
            marker = f"{issue.file_path}:{issue.line_number or 'n/a'}"
            issue_refs.append(marker)
        issue_ref_text = ", ".join(issue_refs) if issue_refs else "none"

        if text:
            return (
                f"{text}\n"
                f"Verified references: files[{file_refs}] issues[{issue_ref_text}]"
            )
        return f"Verified references: files[{file_refs}] issues[{issue_ref_text}]"


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
        log_target = os.environ.get("GITHUB_AGENT_CRITIC_LOG", ".github_agent_logs/critic_reflections.jsonl")
        self._critic_log_path = Path(log_target)

    def reflect(
        self,
        draft: Union[IssueDraft, PRDraft],
        reviewer_result: ReviewerResult,
    ) -> ReflectionResult:
        """Critique the draft and return a reflection artifact."""
        if isinstance(draft, IssueDraft):
            draft_dict = {
                "type": "issue",
                "title": draft.title[:140],
                "problem_description": draft.problem_description[:500],
                "evidence": draft.evidence[:500],
                "acceptance_criteria": (draft.acceptance_criteria or [])[:5],
                "risk_level": draft.risk_level,
            }
        else:
            draft_dict = {
                "type": "pr",
                "title": draft.title[:140],
                "summary": draft.summary[:500],
                "files_affected": (draft.files_affected or [])[:6],
                "behavior_change": draft.behavior_change[:400],
                "test_plan": draft.test_plan[:400],
                "risk_level": draft.risk_level,
            }

        actual_evidence = {
            "issues_found": [str(i.message)[:140] for i in (reviewer_result.issues or [])[:6]],
            "files_changed": [f["path"] for f in reviewer_result.files_summary[:6]],
            "risk_level": reviewer_result.risk.level.value
            if reviewer_result.risk
            else "medium",
            "category": reviewer_result.category.value
            if reviewer_result.category
            else "unknown",
        }

        prompt = reflect_prompt(draft=draft_dict, actual_evidence=actual_evidence)

        raw = ""
        parsed: dict = {}
        try:
            raw = self.llm.generate(prompt)
            parsed = parse_json_object(raw)
        except Exception:
            parsed = self._fallback_reflection(draft_dict, actual_evidence)
            raw = ""

        result = self._coerce_reflection(parsed, raw)
        self._log_reflection(result, draft_dict, actual_evidence)
        return result

    @staticmethod
    def _coerce_list_of_str(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if str(v).strip()]

    def _coerce_reflection(self, parsed: dict, raw: str) -> ReflectionResult:
        unsupported_claims = self._coerce_list_of_str(parsed.get("unsupported_claims"))
        missing_evidence = self._coerce_list_of_str(parsed.get("missing_evidence"))
        missing_tests = self._coerce_list_of_str(parsed.get("missing_tests"))
        policy_violations = self._coerce_list_of_str(parsed.get("policy_violations"))
        suggestions = self._coerce_list_of_str(parsed.get("suggestions"))

        overall_quality = str(parsed.get("overall_quality") or "needs_improvement").strip().lower()
        if overall_quality not in ALLOWED_QUALITY:
            overall_quality = "needs_improvement"

        passed = bool(parsed.get("passed", False))
        if policy_violations or overall_quality == "poor":
            passed = False

        return ReflectionResult(
            passed=passed,
            unsupported_claims=unsupported_claims,
            missing_evidence=missing_evidence,
            missing_tests=missing_tests,
            policy_violations=policy_violations,
            suggestions=suggestions,
            overall_quality=overall_quality,
            raw=raw,
        )

    @staticmethod
    def _fallback_reflection(draft: dict, actual_evidence: dict) -> dict:
        """Deterministic fallback when Critic LLM is unavailable/timeouts."""
        missing_evidence = []
        missing_tests = []
        policy_violations = []
        suggestions = []

        if draft.get("type") == "issue":
            if not draft.get("evidence"):
                missing_evidence.append("Evidence section is empty.")
            if not draft.get("acceptance_criteria"):
                missing_tests.append("Acceptance criteria are missing or empty.")
        else:
            if not draft.get("test_plan"):
                missing_tests.append("Test plan is missing or empty.")
            if not draft.get("files_affected"):
                missing_evidence.append("Files affected list is missing or empty.")

        if not actual_evidence.get("files_changed"):
            policy_violations.append("No verified file evidence available for reflection.")
            suggestions.append("Run reflection with review context enabled.")

        if missing_evidence or missing_tests:
            suggestions.append("Add concrete evidence references and testable verification steps.")

        return {
            "passed": not (policy_violations or missing_tests),
            "unsupported_claims": [],
            "missing_evidence": missing_evidence,
            "missing_tests": missing_tests,
            "policy_violations": policy_violations,
            "suggestions": suggestions or ["Proceed with manual gatekeeper review."],
            "overall_quality": "needs_improvement" if (missing_evidence or missing_tests or policy_violations) else "good",
        }

    def _log_reflection(self, result: ReflectionResult, draft: dict, actual_evidence: dict) -> None:
        """Write one JSON line per critic run so issues can be analyzed over time."""
        payload = {
            "ts_utc": dt.datetime.now(dt.UTC).isoformat(),
            "source": "critic_agent",
            "passed": result.passed,
            "overall_quality": result.overall_quality,
            "unsupported_claims": result.unsupported_claims,
            "missing_evidence": result.missing_evidence,
            "missing_tests": result.missing_tests,
            "policy_violations": result.policy_violations,
            "suggestions": result.suggestions,
            "draft_type": draft.get("type", "unknown"),
            "draft_title": str(draft.get("title", ""))[:200],
            "files_changed_count": len(actual_evidence.get("files_changed", []) or []),
            "issues_found_count": len(actual_evidence.get("issues_found", []) or []),
            "risk_level": actual_evidence.get("risk_level", "unknown"),
            "category": actual_evidence.get("category", "unknown"),
            "raw_preview": (result.raw or "")[:500],
        }
        try:
            self._critic_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._critic_log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception:
            # Logging must never break the review pipeline.
            return


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
                tool_evidence={},
            )
            context = {}

        # Writer drafts from instruction
        draft = self.writer.draft_from_instruction(instruction, artifact_type, context)

        # Critic reflects — notes if evidence cannot be verified
        if diff_result and diff_result.files:
            reflection = self.critic.reflect(draft, reviewer_result)
        else:
            reflection = ReflectionResult(
                passed=False,
                unsupported_claims=[
                    "Unable to verify factual claims because no code diff or file evidence was provided."
                ],
                missing_evidence=[
                    "No code diff provided; evidence claims cannot be verified against actual code."
                ],
                missing_tests=[
                    "Cannot validate test adequacy without changed files or executable verification context."
                ],
                policy_violations=[
                    "Evidence verification unavailable in explicit-draft mode without diff context."
                ],
                suggestions=[
                    "Consider providing a repo path and base branch for evidence-based verification."
                ],
                overall_quality="needs_improvement",
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

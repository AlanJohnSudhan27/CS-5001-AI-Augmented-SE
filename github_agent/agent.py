from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from .analyzer import CodeAnalyzer
from .categorizer import ChangeCategorizer, ChangeCategory
from .llm import OllamaLLM
from .prompts import review_decision_prompt
from .reporter import Reporter, ReviewDecision, determine_decision
from .risk_assessor import RiskAssessor, RiskLevel
from .tools import Tools
from .types import AgentConfig, RunResult
from .utils import clamp, parse_json_object


class Agent:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.repo = Path(cfg.repo).resolve()
        self.tools = Tools(self.repo)
        timeout_s = self._llm_timeout_s()
        self.llm = OllamaLLM(model=cfg.model, host=cfg.host, temperature=cfg.temperature)
        self.llm.timeout_s = timeout_s

    def _log(self, message: Any) -> None:
        if self.cfg.verbose:
            print(message)

    def review_branch(self, branch: Optional[str], use_colors: bool = True, render_report: bool = True) -> RunResult:
        if not self.tools.is_git_repo():
            return RunResult(False, "Not a git repository. Run this command in a git repository.")

        current_branch = self.tools.current_branch()
        if not current_branch:
            return RunResult(False, "Could not determine current branch.")

        target_branch = branch or self.tools.default_branch()
        self._log(f"Analyzing branch '{current_branch}' vs '{target_branch}'")
        diff_result = self.tools.diff_from_branch(target_branch)

        if not diff_result.files:
            return RunResult(True, "No changes found.", summary={"files": 0, "target_branch": target_branch})

        # Optional model override for deeper review (disabled by default).
        forced_model = (os.environ.get("REVIEW_FORCE_MODEL", "") or "").strip()
        if forced_model:
            self.llm = OllamaLLM(
                model=forced_model,
                host=self.cfg.host,
                temperature=self.cfg.temperature,
                timeout_s=self._llm_timeout_s(),
            )
        return self._perform_review(
            diff_result=diff_result,
            use_colors=use_colors,
            render_report=render_report,
            commit_messages=None,
            mode="branch",
            target=target_branch,
        )

    def review_commits(self, commit_range: str, use_colors: bool = True, render_report: bool = True) -> RunResult:
        if not self.tools.is_git_repo():
            return RunResult(False, "Not a git repository. Run this command in a git repository.")

        if ".." not in commit_range:
            return RunResult(False, "Commit range must be in format 'start..end'.")

        parts = commit_range.split("..")
        if len(parts) != 2:
            return RunResult(False, "Invalid commit range format. Use 'start..end'.")

        start_commit = parts[0].strip()
        end_commit = parts[1].strip()
        if not start_commit or not end_commit:
            return RunResult(False, "Both start and end commits must be specified.")

        diff_result = self.tools.diff_from_commits(start_commit, end_commit)
        if not diff_result.files:
            return RunResult(True, "No changes found in the specified range.", summary={"files": 0})

        messages = self.tools.commit_messages(start_commit, end_commit)
        return self._perform_review(
            diff_result=diff_result,
            use_colors=use_colors,
            render_report=render_report,
            commit_messages=messages,
            mode="commits",
            target=f"{start_commit}..{end_commit}",
        )

    def _perform_review(
        self,
        diff_result,
        use_colors: bool,
        render_report: bool,
        commit_messages: Optional[list[str]],
        mode: str,
        target: str,
    ) -> RunResult:
        analyzer = CodeAnalyzer()
        categorizer = ChangeCategorizer()
        risk_assessor = RiskAssessor()

        issues = analyzer.analyze_diff(diff_result)
        category = categorizer.categorize(diff_result, commit_messages)
        risk_assessment = risk_assessor.assess(diff_result, issues, category)
        decision, justification = determine_decision(risk_assessment, issues, category)

        llm_override = None
        if not self._is_fast_mode():
            try:
                llm_override = self._model_override(
                    diff_result=diff_result,
                    issues=issues,
                    fallback_category=category,
                    fallback_risk=risk_assessment.level,
                    fallback_decision=decision,
                    fallback_justification=justification,
                    commit_messages=commit_messages or [],
                )
            except Exception as exc:
                # Never fail the review because of LLM/network timeouts.
                self._log(f"Model override failed; using static decision: {exc}")
                llm_override = None

        if llm_override:
            category = llm_override["category"]
            risk_assessment.level = llm_override["risk_level"]
            decision = llm_override["decision"]
            justification = llm_override["justification"]

        if render_report:
            Reporter(use_colors=use_colors).print_review_report(
                diff_result=diff_result,
                issues=issues,
                category=category,
                risk_assessment=risk_assessment,
                decision=decision,
                justification=justification,
            )

        summary = {
            "mode": mode,
            "target": target,
            "files_changed": diff_result.total_files,
            "total_additions": diff_result.total_additions,
            "total_deletions": diff_result.total_deletions,
            "issue_count": len(issues),
            "category": category.value,
            "risk_level": risk_assessment.level.value,
            "decision": decision.value,
            "justification": justification,
            "model": self.cfg.model,
            "host": self.cfg.host,
            "issues": [
                {
                    "severity": issue.severity.value,
                    "type": issue.issue_type.value,
                    "message": issue.message,
                    "file": issue.file_path,
                    "line": issue.line_number,
                }
                for issue in issues[:200]
            ],
            "security_issues": [
                {
                    "severity": issue.severity.value,
                    "type": issue.issue_type.value,
                    "message": issue.message,
                    "file": issue.file_path,
                    "line": issue.line_number,
                }
                for issue in issues
                if issue.issue_type.value == "security"
            ],
            "files": [
                {
                    "path": f.path,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in diff_result.files
            ],
        }
        return RunResult(True, "Review complete.", summary=summary)

    def _model_override(
        self,
        diff_result,
        issues,
        fallback_category: ChangeCategory,
        fallback_risk: RiskLevel,
        fallback_decision: ReviewDecision,
        fallback_justification: str,
        commit_messages: list[str],
    ) -> Optional[dict[str, Any]]:
        fast = self._is_fast_mode()
        max_files = 3 if fast else 10
        max_content = 900 if fast else 4000
        max_issue_items = 20 if fast else 100
        max_file_items = 10 if fast else 50
        max_commits = 8 if fast else 30
        prompt_clamp = 3000 if fast else 14000

        # Gather full file contents for changed files
        file_contents = []
        for file_change in diff_result.files[:max_files]:
            try:
                with open(file_change.path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
                file_contents.append({
                    "path": file_change.path,
                    "content": clamp(content, max_content),
                })
            except Exception:
                continue

        context = {
            "stats": {
                "total_files": diff_result.total_files,
                "total_additions": diff_result.total_additions,
                "total_deletions": diff_result.total_deletions,
            },
            "files": [
                {
                    "path": file_change.path,
                    "status": file_change.status,
                    "additions": file_change.additions,
                    "deletions": file_change.deletions,
                }
                for file_change in diff_result.files[:max_file_items]
            ],
            "issues": [
                {
                    "severity": issue.severity.value,
                    "type": issue.issue_type.value,
                    "message": issue.message,
                    "file": issue.file_path,
                    "line": issue.line_number,
                }
                for issue in issues[:max_issue_items]
            ],
            "commit_messages": commit_messages[:max_commits],
            "fallback": {
                "category": fallback_category.value,
                "risk_level": fallback_risk.value,
                "decision": fallback_decision.value,
                "justification": fallback_justification,
            },
            "file_contents": file_contents,
        }

        # Prompt the LLM to do a full code review, not just summarize static issues.
        prompt = (
            "Role: Senior software reviewer.\n"
            "Objective: perform a full review of changed files and recommend final action.\n"
            "Grounding policy:\n"
            "- Use only provided context, file contents, and static-analysis findings\n"
            "- Do not fabricate files, line numbers, or issue types\n"
            "- If evidence is weak, reflect uncertainty inside justification\n"
            "Output contract:\n"
            "- Return ONLY one valid JSON object\n"
            "- No markdown, no prose before/after JSON\n"
            "- Use double quotes and no trailing commas\n"
            "Reasoning protocol:\n"
            "- Think step-by-step internally\n"
            "- Return only final JSON\n"
            "Schema (exact):\n"
            "{\n"
            "  \"category\": \"feature|bugfix|refactor|documentation|test|chore|style|security|performance\",\n"
            "  \"risk_level\": \"low|medium|high\",\n"
            "  \"decision\": \"create_issue|create_pr|no_action\",\n"
            "  \"justification\": \"string\",\n"
            "  \"issues_found\": [{\"file\": \"string\", \"line\": 1, \"type\": \"string\", \"message\": \"string\"}]\n"
            "}\n"
            "Decision policy:\n"
            "- High-impact security or correctness risk should strongly favor create_issue\n"
            "- Low-risk formatting/doc-only changes should favor no_action\n"
            "- create_pr is for improvement proposals without incident-level urgency\n"
            "Justification must cite concrete evidence from provided context.\n"
            f"\nCONTEXT_JSON:\n{clamp(json.dumps(context, indent=2), prompt_clamp)}\n"
        )
        self._log(prompt)
        try:
            raw = self.llm.generate(prompt)
        except Exception as exc:
            self._log(f"Model override skipped (LLM unavailable): {exc}")
            return None
        self._log(raw)

        try:
            payload = parse_json_object(raw)
        except Exception as exc:
            self._log(f"Model override skipped: {exc}")
            return None

        category = self._to_category(payload.get("category"))
        risk_level = self._to_risk(payload.get("risk_level"))
        decision = self._to_decision(payload.get("decision"))
        justification = str(payload.get("justification") or "").strip()

        if not (category and risk_level and decision and justification):
            self._log("Model override skipped: invalid schema values")
            return None

        return {
            "category": category,
            "risk_level": risk_level,
            "decision": decision,
            "justification": justification,
            "issues_found": payload.get("issues_found", []),
        }

    @staticmethod
    def _llm_timeout_s() -> int:
        return 60

    @staticmethod
    def _is_fast_mode() -> bool:
        return True

    @staticmethod
    def _to_category(value: Any) -> Optional[ChangeCategory]:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        for member in ChangeCategory:
            if member.value == normalized:
                return member
        return None

    @staticmethod
    def _to_risk(value: Any) -> Optional[RiskLevel]:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        for member in RiskLevel:
            if member.value == normalized:
                return member
        return None

    @staticmethod
    def _to_decision(value: Any) -> Optional[ReviewDecision]:
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        for member in ReviewDecision:
            if member.value == normalized:
                return member
        return None

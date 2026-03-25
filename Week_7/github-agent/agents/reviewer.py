"""
Reviewer Agent — analyzes code changes or existing issues/PRs.

Skills: diff_analysis, risk_assessment, change_categorization

Uses MCP tools to fetch real data (git diff, git log, file reads,
GitHub issue/PR content). Never fabricates information.
"""
from __future__ import annotations

import json

from agents.base import BaseA2AAgent, Task
from config import REVIEWER_PORT, MCP_PORT


class ReviewerAgent(BaseA2AAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Reviewer",
            description="Analyzes code changes, categorizes them, assesses risk, and recommends actions.",
            skills=["diff_analysis", "risk_assessment", "change_categorization"],
            port=REVIEWER_PORT,
            mcp_url=f"http://localhost:{MCP_PORT}/sse",
        )

    async def handle(self, task: Task) -> str:
        message = task.message
        context = task.context

        # Determine task type from the message
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            request = {"type": "review", "repo_path": message}

        task_type = request.get("type", "review")

        if task_type == "improve_issue":
            return await self._critique_issue(request)
        elif task_type == "improve_pr":
            return await self._critique_pr(request)
        else:
            return await self._review_changes(request)

    # ------------------------------------------------------------------
    # Review code changes
    # ------------------------------------------------------------------

    async def _review_changes(self, request: dict) -> str:
        repo_path = request.get("repo_path", ".")
        commit_range = request.get("commit_range", "")

        # Fetch real data via MCP tools
        diff_output = await self.mcp_call("git_diff", repo_path=repo_path, commit_range=commit_range)
        log_output = await self.mcp_call("git_log", repo_path=repo_path, max_count=5)

        prompt = f"""You are a senior code reviewer. Analyze the following git diff and recent commit log.

The diff may come from uncommitted working tree changes OR from the last commit if no
uncommitted changes were found. Either way, analyze the actual code changes shown.

## Git Diff
```
{diff_output}
```

## Recent Commits
```
{log_output}
```

Respond ONLY with valid JSON (no markdown fences, no extra text) in this exact format:
{{
  "category": "feature | bugfix | refactor | docs | test | config",
  "risk_level": "low | medium | high",
  "issues": ["list of potential issues found"],
  "improvements": ["list of suggested improvements"],
  "recommended_action": "create_issue | create_pr | no_action",
  "justification": "evidence-based explanation for your recommendation",
  "files_affected": ["list of files changed"],
  "summary": "brief summary of what changed"
}}

Rules:
- Base your analysis ONLY on the actual diff content shown above
- Do NOT fabricate or assume any information not present in the diff
- Justify every finding with specific evidence from the diff
- If the diff contains code changes, you MUST analyze them — even if they come from recent commits rather than uncommitted work
- Only recommend "no_action" if the diff is literally empty or contains no meaningful code changes
"""
        return await self.llm_call(prompt)

    # ------------------------------------------------------------------
    # Critique existing issue
    # ------------------------------------------------------------------

    async def _critique_issue(self, request: dict) -> str:
        owner = request["owner"]
        repo = request["repo"]
        issue_number = request["issue_number"]

        issue_data = await self.mcp_call(
            "github_get_issue", owner=owner, repo=repo, issue_number=issue_number
        )

        prompt = f"""You are a technical writing critic. Analyze this GitHub issue for quality.

## Issue Content
{issue_data}

Respond ONLY with valid JSON (no markdown fences, no extra text) in this exact format:
{{
  "critique": {{
    "unclear_sections": ["list of vague or unclear sections"],
    "missing_information": ["list of missing details"],
    "vague_language": ["list of vague phrases found"],
    "missing_acceptance_criteria": true/false,
    "missing_reproduction_steps": true/false
  }},
  "original_title": "the current title",
  "original_body": "the current body",
  "severity": "minor | moderate | major"
}}

Be specific — quote exact phrases that are vague or unclear.
"""
        return await self.llm_call(prompt)

    # ------------------------------------------------------------------
    # Critique existing PR
    # ------------------------------------------------------------------

    async def _critique_pr(self, request: dict) -> str:
        owner = request["owner"]
        repo = request["repo"]
        pr_number = request["pr_number"]

        pr_data = await self.mcp_call(
            "github_get_pr", owner=owner, repo=repo, pr_number=pr_number
        )

        prompt = f"""You are a technical writing critic. Analyze this GitHub pull request for quality.

## PR Content
{pr_data}

Respond ONLY with valid JSON (no markdown fences, no extra text) in this exact format:
{{
  "critique": {{
    "unclear_sections": ["list of vague or unclear sections"],
    "missing_information": ["list of missing details"],
    "vague_language": ["list of vague phrases found"],
    "missing_test_plan": true/false,
    "missing_behavior_change": true/false
  }},
  "original_title": "the current title",
  "original_body": "the current body",
  "severity": "minor | moderate | major"
}}

Be specific — quote exact phrases that are vague or unclear.
"""
        return await self.llm_call(prompt)

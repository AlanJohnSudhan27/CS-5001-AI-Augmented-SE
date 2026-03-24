"""
Writer Agent — drafts GitHub issue or PR content.

Skills: issue_drafting, pr_drafting, content_improvement

Takes the Planner's structured plan as context and produces
a complete, well-formatted draft. Can use MCP tools for
additional evidence gathering.
"""
from __future__ import annotations

import json

from agents.base import BaseA2AAgent, Task
from config import WRITER_PORT, MCP_PORT


class WriterAgent(BaseA2AAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Writer",
            description="Drafts GitHub issue and PR content based on structured plans.",
            skills=["issue_drafting", "pr_drafting", "content_improvement"],
            port=WRITER_PORT,
            mcp_url=f"http://localhost:{MCP_PORT}/sse",
        )

    async def handle(self, task: Task) -> str:
        message = task.message
        context = task.context  # Planner's output

        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            request = {"action_type": "issue"}

        action_type = request.get("action_type", "issue")

        if action_type in ("improve_issue", "improve_pr"):
            return await self._write_improvement(request, context)
        elif action_type == "pr":
            return await self._write_pr(request, context)
        else:
            return await self._write_issue(request, context)

    # ------------------------------------------------------------------
    # Draft a new issue
    # ------------------------------------------------------------------

    async def _write_issue(self, request: dict, context: str) -> str:
        prompt = f"""You are a technical writer creating a GitHub issue.

## Plan from Planner Agent
{context}

## Original Request
{json.dumps(request, indent=2)}

Write a complete GitHub issue. Respond ONLY with valid JSON (no markdown fences, no extra text):
{{
  "title": "concise issue title",
  "body": "full markdown body of the issue",
  "labels": ["suggested labels"],
  "draft_type": "issue"
}}

The body MUST include these sections in markdown:
## Problem Description
(What is the problem? Be specific.)

## Evidence
(Cite specific findings from the review. Include file names, line references, diff snippets.)

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Risk Level
(low/medium/high with justification)

Rules:
- Every claim must be backed by evidence from the plan/review
- Do NOT fabricate file names, function names, or line numbers
- Use proper markdown formatting
"""
        return await self.llm_call(prompt)

    # ------------------------------------------------------------------
    # Draft a new PR
    # ------------------------------------------------------------------

    async def _write_pr(self, request: dict, context: str) -> str:
        prompt = f"""You are a technical writer creating a GitHub pull request description.

## Plan from Planner Agent
{context}

## Original Request
{json.dumps(request, indent=2)}

Write a complete GitHub PR. Respond ONLY with valid JSON (no markdown fences, no extra text):
{{
  "title": "concise PR title",
  "body": "full markdown body of the PR",
  "labels": ["suggested labels"],
  "draft_type": "pr"
}}

The body MUST include these sections in markdown:
## Summary
(What does this PR do? Brief overview.)

## Files Affected
(List the files changed and what changed in each.)

## Behavior Change
(What behavior changed? Before vs after.)

## Test Plan
- [ ] Test step 1
- [ ] Test step 2

## Risk Level
(low/medium/high with justification)

Rules:
- Every claim must be backed by evidence from the plan/review
- Do NOT fabricate file names, function names, or line numbers
- Use proper markdown formatting
"""
        return await self.llm_call(prompt)

    # ------------------------------------------------------------------
    # Write improvement for existing issue/PR
    # ------------------------------------------------------------------

    async def _write_improvement(self, request: dict, context: str) -> str:
        prompt = f"""You are a technical writer improving an existing GitHub issue or PR.

## Plan from Planner Agent (includes critique of original)
{context}

## Original Request
{json.dumps(request, indent=2)}

Write an improved version. Respond ONLY with valid JSON (no markdown fences, no extra text):
{{
  "title": "improved title",
  "body": "improved full markdown body",
  "changes_made": ["list of specific improvements made"],
  "draft_type": "improvement"
}}

Rules:
- Address every critique point from the plan
- Add missing acceptance criteria or test plans
- Replace vague language with specific, measurable descriptions
- Preserve any good content from the original
- Do NOT fabricate information not supported by the context
"""
        return await self.llm_call(prompt)

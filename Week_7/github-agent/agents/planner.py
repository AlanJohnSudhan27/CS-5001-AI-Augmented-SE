"""
Planner Agent — produces a structured action plan before drafting.

Skills: action_planning, task_structuring

Implements the Planning Pattern: receives the Reviewer's output as context
and produces a structured plan that the Writer will follow.
No MCP tools needed — works entirely from context.
"""
from __future__ import annotations

import json

from agents.base import BaseA2AAgent, Task
from config import PLANNER_PORT


class PlannerAgent(BaseA2AAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Planner",
            description="Creates structured action plans for issue/PR drafting based on review output.",
            skills=["action_planning", "task_structuring"],
            port=PLANNER_PORT,
        )

    async def handle(self, task: Task) -> str:
        message = task.message
        context = task.context  # Reviewer's output

        # Determine if this is from explicit instruction or review
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            request = {"instruction": message}

        action_type = request.get("action_type", "auto")

        prompt = f"""You are a technical project planner. Based on the review analysis below,
create a structured plan for drafting content.

## Review Analysis (from Reviewer Agent)
{context}

## User Request
{json.dumps(request, indent=2)}

Respond ONLY with valid JSON (no markdown fences, no extra text) in this exact format:
{{
  "action_type": "issue | pr | improve_issue | improve_pr",
  "structure": {{
    "title_guidance": "guidance for the title",
    "sections": [
      {{
        "heading": "section name",
        "purpose": "what this section should contain",
        "evidence_needed": ["specific evidence to include from the review"]
      }}
    ]
  }},
  "key_points": ["most important points to address"],
  "risk_level": "low | medium | high",
  "evidence_to_include": ["specific findings from the review that must be cited"]
}}

Rules:
- For issues: plan sections for Problem Description, Evidence, Acceptance Criteria, Risk Level
- For PRs: plan sections for Summary, Files Affected, Behavior Change, Test Plan, Risk Level
- For improvements: plan sections for Current Issues, Proposed Changes, Improved Content
- Reference specific findings from the review — do not add new claims
- The plan must be actionable enough for a Writer agent to produce a complete draft
"""
        return await self.llm_call(prompt)

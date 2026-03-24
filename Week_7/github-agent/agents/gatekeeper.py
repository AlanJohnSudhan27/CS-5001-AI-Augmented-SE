"""
Gatekeeper Agent — implements the Reflection Pattern.

Skills: safety_verification, reflection, policy_enforcement

Reviews the Writer's draft for quality, accuracy, and policy compliance.
Produces a structured reflection artifact. Does NOT submit anything —
only approves or flags issues for human review.
"""
from __future__ import annotations

from agents.base import BaseA2AAgent, Task
from config import GATEKEEPER_PORT


class GatekeeperAgent(BaseA2AAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Gatekeeper",
            description="Verifies draft quality, checks for unsupported claims, and enforces human approval.",
            skills=["safety_verification", "reflection", "policy_enforcement"],
            port=GATEKEEPER_PORT,
        )

    async def handle(self, task: Task) -> str:
        # message = Writer's draft, context = original review + plan
        draft = task.message
        context = task.context

        prompt = f"""You are a strict quality gatekeeper. Your job is to review a draft
GitHub issue or PR before it is shown to a human for approval.

## Draft to Review
{draft}

## Original Review & Plan Context
{context}

Perform these checks:
1. **Unsupported Claims**: Does the draft make claims not backed by evidence in the context?
2. **Missing Evidence**: Are there sections that should cite specific code/diff but don't?
3. **Missing Tests**: If this is a PR or behavioral change, is there a test plan?
4. **Policy Violations**: Does the draft contain anything inappropriate, offensive, or misleading?
5. **Vague Language**: Are there phrases that are too vague to be actionable?
6. **Completeness**: Does the draft have all required sections?

Respond ONLY with valid JSON (no markdown fences, no extra text):
{{
  "approved": true/false,
  "reflection": {{
    "unsupported_claims": ["list any claims not backed by evidence"],
    "missing_evidence": ["list sections that need more evidence"],
    "missing_tests": ["list missing test coverage"],
    "policy_violations": ["list any policy issues"],
    "vague_language": ["list vague phrases that should be more specific"],
    "completeness_issues": ["list any missing required sections"]
  }},
  "summary": "brief overall assessment",
  "suggestions": "specific suggestions for improvement if not approved",
  "revised_draft": null
}}

Rules:
- Set "approved" to true ONLY if ALL checks pass
- Be specific — quote exact text that is problematic
- If not approved, provide actionable suggestions
- Do NOT rewrite the draft unless critical issues exist (set revised_draft to the rewrite or null)
"""
        return await self.llm_call(prompt)

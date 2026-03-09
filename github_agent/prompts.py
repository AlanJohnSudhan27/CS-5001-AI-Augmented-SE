from __future__ import annotations

import json


def _json_only_output_contract() -> str:
    return (
        "Output contract:\n"
        "- Return ONLY a single valid JSON object\n"
        "- No markdown fences, no commentary, no extra keys\n"
        "- Use double quotes for all JSON strings\n"
        "- Do not use trailing commas\n"
    )


def _grounding_contract() -> str:
    return (
        "Grounding policy:\n"
        "- Use only evidence present in the provided context\n"
        "- Do not fabricate files, line numbers, tests, or behavior\n"
        "- If evidence is limited, state that limitation inside existing fields\n"
    )


def _reasoning_contract() -> str:
    return (
        "Reasoning protocol:\n"
        "- Think step-by-step internally before writing final JSON\n"
        "- Resolve conflicts by prioritizing explicit schema/rules\n"
        "- Final answer must include only the JSON object\n"
    )


# ---------------------------------------------------------------------------
# Task 1 - Review decision prompt
# ---------------------------------------------------------------------------


def review_decision_prompt(context_json: str) -> str:
    return (
        "Role: Senior software reviewer deciding final GitHub action.\n"
        "Objective: classify the change, assess risk, and recommend action.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_grounding_contract()}\n"
        f"{_reasoning_contract()}\n"
        "Schema (exact):\n"
        "{\n"
        '  "category": "feature|bugfix|refactor|documentation|test|chore|style|security|performance",\n'
        '  "risk_level": "low|medium|high",\n'
        '  "decision": "create_issue|create_pr|no_action",\n'
        '  "justification": "string"\n'
        "}\n\n"
        "Decision policy:\n"
        "- Security findings or high operational risk should strongly favor create_issue\n"
        "- Pure documentation/style changes with no meaningful risk should favor no_action\n"
        "- create_pr is for constructive change proposals without incident-level urgency\n"
        "- justification must be concise, specific, and evidence-based\n\n"
        f"CONTEXT_JSON:\n{context_json}\n"
    )


# ---------------------------------------------------------------------------
# Reviewer Agent - deep analysis prompt (Tool Use Pattern)
# ---------------------------------------------------------------------------


def reviewer_deep_analysis_prompt(
    diff_snippet: str,
    issues: list,
    category: str,
    risk_level: str,
) -> str:
    issues_json = json.dumps(issues[:20], indent=2)
    return (
        "Role: Reviewer Agent performing deep technical code review.\n"
        "Goal: explain what changed, what risks remain, and whether the patch is coherent.\n"
        "Evidence constraint: base all claims only on provided diff and issue list.\n\n"
        f"{_grounding_contract()}\n"
        "Output format:\n"
        "- 3 to 5 short paragraphs\n"
        "- Include concrete file references present in the diff snippet\n"
        "- No bullet lists or markdown headings\n\n"
        f"CATEGORY: {category}\n"
        f"RISK LEVEL: {risk_level}\n\n"
        f"PRE-DETECTED STATIC ANALYSIS ISSUES:\n{issues_json}\n\n"
        f"GIT DIFF SNIPPET:\n{diff_snippet}\n\n"
        "Cover all points:\n"
        "1. What these changes do (inferred from the diff)\n"
        "2. Potential risks not captured by static analysis\n"
        "3. Code quality observations with file references\n"
        "4. Whether changes appear complete and coherent\n\n"
        "If critical evidence is missing, call out the exact missing evidence."
    )


# ---------------------------------------------------------------------------
# Reviewer Agent - critique of existing GitHub issue or PR (Task 3)
# ---------------------------------------------------------------------------


def reviewer_existing_content_prompt(content: dict, content_type: str) -> str:
    title = content.get("title", "")
    body = (content.get("body") or "")[:2500]
    return (
        f"Role: Reviewer Agent critiquing an existing GitHub {content_type}.\n"
        "Objective: find clarity, completeness, evidence, and structure gaps.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"EXISTING {content_type.upper()} TITLE: {title}\n\n"
        f"EXISTING {content_type.upper()} BODY:\n{body}\n\n"
        "Return JSON with this exact schema:\n"
        "{\n"
        '  "vague_language": ["specific vague phrase or sentence from the original"],\n'
        '  "missing_information": ["what specific information is missing"],\n'
        '  "unclear_criteria": ["which acceptance criteria or test steps are unclear or missing"],\n'
        '  "missing_evidence": ["what evidence or context is not referenced"],\n'
        '  "structural_problems": ["structural issues e.g. missing sections"],\n'
        '  "overall_assessment": "one-sentence overall assessment",\n'
        '  "severity": "minor|moderate|major"\n'
        "}\n"
    )


# ---------------------------------------------------------------------------
# Planner Agent - structured planning before drafting (Planning Pattern)
# ---------------------------------------------------------------------------


def planner_prompt(context_json: str) -> str:
    return (
        "Role: Planner Agent.\n"
        "Objective: produce a structured plan before drafting any content.\n"
        "The plan must specify required sections, evidence, and rationale.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_grounding_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"ANALYSIS CONTEXT:\n{context_json}\n\n"
        "Schema:\n"
        "{\n"
        '  "artifact_type": "issue|pr",\n'
        '  "sections": ["section names to include in the draft"],\n'
        '  "key_points": ["specific points the draft must address"],\n'
        '  "evidence": ["concrete evidence items from the analysis to cite"],\n'
        '  "rationale": "why this action is warranted based on the evidence"\n'
        "}\n\n"
        "Planning rules:\n"
        "- For issues: sections must include problem_description, evidence, acceptance_criteria, risk_level\n"
        "- For PRs: sections must include summary, files_affected, behavior_change, test_plan, risk_level\n"
        "- Evidence must come from actual issues/files in context\n"
        "- Prefer citing tool_evidence ids (file-*, issue-*, commit-*) when available\n"
        "- Rationale must reference specific findings\n"
        "- If uncertain, still produce a complete plan using conservative, evidence-backed defaults\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent - draft GitHub Issue (Task 2)
# ---------------------------------------------------------------------------


def draft_issue_prompt(plan: dict, context: dict) -> str:
    plan_json = json.dumps(plan, indent=2)
    context_json = json.dumps(context, indent=2)
    return (
        "Role: Writer Agent drafting a GitHub Issue.\n"
        "Goal: produce an actionable issue aligned with planner output.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_grounding_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"PLAN:\n{plan_json}\n\n"
        f"CODE CONTEXT (actual diff data - cite specific files/issues):\n{context_json}\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "concise issue title under 80 characters",\n'
        '  "problem_description": "clear description of the problem and its impact",\n'
        '  "evidence": "specific evidence from code - file names, line references, patterns",\n'
        '  "acceptance_criteria": ["specific testable criterion 1", "criterion 2"],\n'
        '  "risk_level": "low|medium|high",\n'
        '  "labels": ["suggested GitHub label"]\n'
        "}\n\n"
        "Writing rules:\n"
        "- Do not fabricate evidence not present in context\n"
        "- Acceptance criteria must be testable and concrete\n"
        "- Title must be actionable and specific\n"
        "- Evidence must reference actual files from context\n"
        "- Prefer references traceable to tool_evidence entries when provided\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent - draft GitHub PR description (Task 2)
# ---------------------------------------------------------------------------


def draft_pr_prompt(plan: dict, context: dict) -> str:
    plan_json = json.dumps(plan, indent=2)
    context_json = json.dumps(context, indent=2)
    return (
        "Role: Writer Agent drafting a GitHub Pull Request description.\n"
        "Goal: produce a reviewer-ready PR description aligned with the plan.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_grounding_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"PLAN:\n{plan_json}\n\n"
        f"CODE CONTEXT (actual diff data - cite specific files/issues):\n{context_json}\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "concise PR title (follow conventional commits if applicable)",\n'
        '  "summary": "what this PR does and why - reference actual changed files",\n'
        '  "files_affected": ["key file path 1", "key file path 2"],\n'
        '  "behavior_change": "specific observable behavior changes this PR introduces",\n'
        '  "test_plan": "concrete steps to verify changes work correctly",\n'
        '  "risk_level": "low|medium|high"\n'
        "}\n\n"
        "Writing rules:\n"
        "- Files affected must come from the actual diff context\n"
        "- Behavior change must be specific and observable\n"
        "- Test plan must be actionable (not only 'run existing tests')\n"
        "- Do not fabricate details not present in context\n"
        "- Prefer references traceable to tool_evidence entries when provided\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent - draft from explicit user instruction (Task 2, explicit mode)
# ---------------------------------------------------------------------------


def explicit_draft_prompt(instruction: str, artifact_type: str, context: dict) -> str:
    context_str = json.dumps(context, indent=2) if context else "No code context provided."
    if artifact_type == "issue":
        schema = (
            "{\n"
            '  "title": "issue title",\n'
            '  "problem_description": "problem description based on the instruction",\n'
            '  "evidence": "evidence (state based on instruction if no code context)",\n'
            '  "acceptance_criteria": ["specific testable criterion 1", "criterion 2"],\n'
            '  "risk_level": "low|medium|high",\n'
            '  "labels": ["suggested label"]\n'
            "}"
        )
    else:
        schema = (
            "{\n"
            '  "title": "PR title",\n'
            '  "summary": "what and why",\n'
            '  "files_affected": ["files mentioned in instruction or context"],\n'
            '  "behavior_change": "expected behavior change",\n'
            '  "test_plan": "how to verify the changes",\n'
            '  "risk_level": "low|medium|high"\n'
            "}"
        )
    return (
        f"Role: Writer Agent drafting a GitHub {artifact_type.upper()} from explicit instruction.\n"
        "Goal: produce a specific, actionable draft while avoiding invented details.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"USER INSTRUCTION:\n{instruction}\n\n"
        f"CODE CONTEXT (if available):\n{context_str}\n\n"
        "Schema:\n"
        f"{schema}\n\n"
        "Writing rules:\n"
        "- Base the draft on the instruction and be specific/actionable\n"
        "- Do not fabricate technical details not mentioned in instruction or context\n"
        "- If no code context exists, note evidence is based on the instruction\n"
        "- If tool_evidence exists, prioritize it over general assumptions\n"
    )


# ---------------------------------------------------------------------------
# Critic Agent - reflection on draft quality (Reflection Pattern)
# ---------------------------------------------------------------------------


def reflect_prompt(draft: dict, actual_evidence: dict) -> str:
    draft_json = json.dumps(draft, indent=2)
    evidence_json = json.dumps(actual_evidence, indent=2)
    return (
        "Role: Critic Agent performing reflection review on a draft artifact.\n"
        "Goal: block weak or unsupported drafts before human approval.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_grounding_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"DRAFT TO REVIEW:\n{draft_json}\n\n"
        f"ACTUAL EVIDENCE AVAILABLE (from code analysis):\n{evidence_json}\n\n"
        "Check for:\n"
        "1. Unsupported claims - statements not backed by evidence\n"
        "2. Missing evidence - key findings not cited\n"
        "3. Missing tests - weak test plan or non-testable acceptance criteria\n"
        "4. Policy violations - vague language, missing required sections, non-actionable text\n\n"
        "Schema:\n"
        "{\n"
        '  "passed": true,\n'
        '  "unsupported_claims": ["claim text that lacks evidence"],\n'
        '  "missing_evidence": ["evidence that should be cited but is not"],\n'
        '  "missing_tests": ["missing test steps or non-testable acceptance criteria"],\n'
        '  "policy_violations": ["vague language or missing required section"],\n'
        '  "suggestions": ["specific actionable improvement suggestion"],\n'
        '  "overall_quality": "good|needs_improvement|poor"\n'
        "}\n\n"
        "Scoring rules:\n"
        '- "passed" = true only if draft is evidence-based, complete, and has no major gaps\n'
        "- Be specific in critique and quote phrases from draft when possible\n"
        '- "needs_improvement" overall_quality is acceptable and can still pass\n'
        '- Set passed=false for "poor" quality or when policy_violations are present\n'
        "- Always populate all four check lists (unsupported_claims, missing_evidence, missing_tests, policy_violations), even if empty\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent - improve existing Issue (Task 3)
# ---------------------------------------------------------------------------


def improve_issue_prompt(existing_issue: dict) -> str:
    title = existing_issue.get("title", "")
    body = (existing_issue.get("body") or "")[:2500]
    labels = [lbl.get("name", "") for lbl in existing_issue.get("labels", [])]
    return (
        "Role: Writer Agent improving an existing GitHub Issue.\n"
        "Goal: preserve intent while improving clarity, precision, and actionability.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"EXISTING TITLE: {title}\n"
        f"EXISTING LABELS: {labels}\n\n"
        f"EXISTING BODY:\n{body}\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "improved title - specific and actionable",\n'
        '  "problem_description": "improved problem description - remove vague language",\n'
        '  "evidence": "evidence section - specific files/patterns referenced",\n'
        '  "acceptance_criteria": ["specific testable criterion 1", "criterion 2"],\n'
        '  "risk_level": "low|medium|high",\n'
        '  "labels": ["suggested labels"]\n'
        "}\n\n"
        "Rewriting rules:\n"
        "- Remove vague words: 'various', 'some', 'stuff', 'things', 'etc.'\n"
        "- Add specific acceptance criteria if missing or non-testable\n"
        "- Keep essence of original; improve structure and specificity\n"
        "- Do not invent new technical content not implied by original\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent - improve existing PR (Task 3)
# ---------------------------------------------------------------------------


def improve_pr_prompt(existing_pr: dict) -> str:
    title = existing_pr.get("title", "")
    body = (existing_pr.get("body") or "")[:2500]
    base_ref = existing_pr.get("base", {}).get("ref", "")
    head_ref = existing_pr.get("head", {}).get("ref", "")
    return (
        "Role: Writer Agent improving an existing GitHub Pull Request description.\n"
        "Goal: preserve intent while improving reviewer clarity and completeness.\n\n"
        f"{_json_only_output_contract()}\n"
        f"{_reasoning_contract()}\n"
        f"EXISTING TITLE: {title}\n"
        f"BASE BRANCH: {base_ref}  HEAD BRANCH: {head_ref}\n\n"
        f"EXISTING BODY:\n{body}\n\n"
        "Schema:\n"
        "{\n"
        '  "title": "improved PR title (conventional commits style if appropriate)",\n'
        '  "summary": "clear summary of WHAT this PR does and WHY",\n'
        '  "files_affected": ["key files changed (infer from context if mentioned)"],\n'
        '  "behavior_change": "specific observable behavior changes",\n'
        '  "test_plan": "concrete actionable test steps",\n'
        '  "risk_level": "low|medium|high"\n'
        "}\n\n"
        "Rewriting rules:\n"
        "- Remove vague language: 'various', 'some changes', 'stuff', 'etc.'\n"
        "- Test plan must be actionable steps, not just 'run tests'\n"
        "- Behavior change must be specific and observable\n"
        "- Keep essence of original; improve structure and completeness\n"
    )

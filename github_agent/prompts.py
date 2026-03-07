from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# Task 1 – Review decision prompt (existing, unchanged)
# ---------------------------------------------------------------------------


def review_decision_prompt(context_json: str) -> str:
    return (
        "You are a senior software reviewer.\n"
        "Given git-change analysis context, return only JSON for final review guidance.\n\n"
        "Output requirements:\n"
        "- Return ONLY valid JSON\n"
        "- No markdown, no prose outside JSON\n"
        "- Schema must be exactly:\n"
        "  {\n"
        "    \"category\": \"feature|bugfix|refactor|documentation|test|chore|style|security|performance\",\n"
        "    \"risk_level\": \"low|medium|high\",\n"
        "    \"decision\": \"create_issue|create_pr|no_action\",\n"
        "    \"justification\": \"string\"\n"
        "  }\n\n"
        "Rules:\n"
        "- Prioritize security issues and high risk for create_issue.\n"
        "- Prefer no_action for purely documentation/style updates with no meaningful issues.\n"
        "- Keep justification concise and evidence-based.\n\n"
        f"CONTEXT_JSON:\n{context_json}\n"
    )


# ---------------------------------------------------------------------------
# Reviewer Agent – deep analysis prompt (Tool Use Pattern)
# ---------------------------------------------------------------------------


def reviewer_deep_analysis_prompt(
    diff_snippet: str,
    issues: list,
    category: str,
    risk_level: str,
) -> str:
    issues_json = json.dumps(issues[:20], indent=2)
    return (
        "You are the Reviewer Agent performing a deep technical code review.\n"
        "Analyze the git diff below and provide a concise technical assessment.\n"
        "Base ALL observations on actual content visible in the diff — no speculation.\n\n"
        f"CATEGORY: {category}\n"
        f"RISK LEVEL: {risk_level}\n\n"
        f"PRE-DETECTED STATIC ANALYSIS ISSUES:\n{issues_json}\n\n"
        f"GIT DIFF SNIPPET:\n{diff_snippet}\n\n"
        "Provide a brief technical assessment covering:\n"
        "1. What these changes actually do (inferred from the diff)\n"
        "2. Potential risks not captured by static analysis\n"
        "3. Code quality observations with file references\n"
        "4. Whether the changes appear complete and coherent\n\n"
        "Keep your response to 3-5 paragraphs. Reference specific files/patterns you see."
    )


# ---------------------------------------------------------------------------
# Reviewer Agent – critique of existing GitHub issue or PR (Task 3)
# ---------------------------------------------------------------------------


def reviewer_existing_content_prompt(content: dict, content_type: str) -> str:
    title = content.get("title", "")
    body = (content.get("body") or "")[:2500]
    return (
        f"You are the Reviewer Agent critiquing an existing GitHub {content_type}.\n"
        "Identify ALL problems with clarity, completeness, and structure.\n\n"
        f"EXISTING {content_type.upper()} TITLE: {title}\n\n"
        f"EXISTING {content_type.upper()} BODY:\n{body}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
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
# Planner Agent – structured planning before drafting (Planning Pattern)
# ---------------------------------------------------------------------------


def planner_prompt(context_json: str) -> str:
    return (
        "You are the Planner Agent. Your job is to create a structured plan BEFORE any content is drafted.\n"
        "This plan will guide the Writer Agent — it determines what sections to include,\n"
        "what evidence to cite, and why the action is warranted.\n\n"
        f"ANALYSIS CONTEXT:\n{context_json}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "artifact_type": "issue|pr",\n'
        '  "sections": ["section names to include in the draft"],\n'
        '  "key_points": ["specific points the draft must address"],\n'
        '  "evidence": ["concrete evidence items from the analysis to cite"],\n'
        '  "rationale": "why this action is warranted based on the evidence"\n'
        "}\n\n"
        "Rules:\n"
        "- For issues: sections must include problem_description, evidence, acceptance_criteria, risk_level\n"
        "- For PRs: sections must include summary, files_affected, behavior_change, test_plan, risk_level\n"
        "- Evidence must come from actual issues/files in the context — no speculation\n"
        "- Rationale must reference specific findings\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent – draft GitHub Issue (Task 2)
# ---------------------------------------------------------------------------


def draft_issue_prompt(plan: dict, context: dict) -> str:
    plan_json = json.dumps(plan, indent=2)
    context_json = json.dumps(context, indent=2)
    return (
        "You are the Writer Agent. Draft a complete, professional GitHub Issue\n"
        "following the plan produced by the Planner Agent.\n\n"
        f"PLAN:\n{plan_json}\n\n"
        f"CODE CONTEXT (actual diff data — cite specific files/issues):\n{context_json}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "title": "concise issue title under 80 characters",\n'
        '  "problem_description": "clear description of the problem and its impact",\n'
        '  "evidence": "specific evidence from the code — file names, line references, patterns",\n'
        '  "acceptance_criteria": ["specific testable criterion 1", "criterion 2"],\n'
        '  "risk_level": "low|medium|high",\n'
        '  "labels": ["suggested GitHub label"]\n'
        "}\n\n"
        "Rules:\n"
        "- Do NOT fabricate evidence not present in the context\n"
        "- Acceptance criteria must be testable and concrete\n"
        "- Title must be actionable and specific\n"
        "- Evidence must reference actual files from the context\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent – draft GitHub PR description (Task 2)
# ---------------------------------------------------------------------------


def draft_pr_prompt(plan: dict, context: dict) -> str:
    plan_json = json.dumps(plan, indent=2)
    context_json = json.dumps(context, indent=2)
    return (
        "You are the Writer Agent. Draft a complete, professional GitHub Pull Request description\n"
        "following the plan produced by the Planner Agent.\n\n"
        f"PLAN:\n{plan_json}\n\n"
        f"CODE CONTEXT (actual diff data — cite specific files/issues):\n{context_json}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "title": "concise PR title (follow conventional commits if applicable)",\n'
        '  "summary": "what this PR does and why — reference actual changed files",\n'
        '  "files_affected": ["key file path 1", "key file path 2"],\n'
        '  "behavior_change": "specific observable behavior changes this PR introduces",\n'
        '  "test_plan": "concrete steps to verify the changes work correctly",\n'
        '  "risk_level": "low|medium|high"\n'
        "}\n\n"
        "Rules:\n"
        "- Files affected must come from the actual diff context\n"
        "- Behavior change must be specific and observable\n"
        "- Test plan must be actionable (not just 'run existing tests')\n"
        "- Do NOT fabricate details not present in the context\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent – draft from explicit user instruction (Task 2, explicit mode)
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
        f"You are the Writer Agent. Draft a GitHub {artifact_type.upper()} based on explicit instructions.\n\n"
        f"USER INSTRUCTION:\n{instruction}\n\n"
        f"CODE CONTEXT (if available):\n{context_str}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        f"{schema}\n\n"
        "Rules:\n"
        "- Base the draft on the instruction — be specific and actionable\n"
        "- Do not fabricate technical details not mentioned in the instruction\n"
        "- If no code context is provided, note that evidence is based on the description\n"
    )


# ---------------------------------------------------------------------------
# Critic Agent – reflection on draft quality (Reflection Pattern)
# ---------------------------------------------------------------------------


def reflect_prompt(draft: dict, actual_evidence: dict) -> str:
    draft_json = json.dumps(draft, indent=2)
    evidence_json = json.dumps(actual_evidence, indent=2)
    return (
        "You are the Critic Agent performing a reflection review on a draft GitHub artifact.\n"
        "Your job is to check for quality and accuracy problems BEFORE the draft goes to the user.\n\n"
        f"DRAFT TO REVIEW:\n{draft_json}\n\n"
        f"ACTUAL EVIDENCE AVAILABLE (from code analysis):\n{evidence_json}\n\n"
        "Check for:\n"
        "1. Unsupported claims — things stated in the draft not backed by actual evidence\n"
        "2. Missing evidence — important findings from the code not cited in the draft\n"
        "3. Missing tests — for PRs: inadequate test plan; for issues: non-testable criteria\n"
        "4. Policy violations — vague language, missing required sections, non-actionable items\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "passed": true,\n'
        '  "unsupported_claims": ["claim text that lacks evidence"],\n'
        '  "missing_evidence": ["evidence that should be cited but is not"],\n'
        '  "missing_tests": ["missing test steps or non-testable acceptance criteria"],\n'
        '  "policy_violations": ["vague language or missing required section"],\n'
        '  "suggestions": ["specific actionable improvement suggestion"],\n'
        '  "overall_quality": "good|needs_improvement|poor"\n'
        "}\n\n"
        "Rules:\n"
        '- "passed" = true only if the draft is evidence-based, complete, and has no major gaps\n'
        "- Be specific in critique — quote actual phrases from the draft when possible\n"
        '- "needs_improvement" overall_quality is acceptable and still passes review\n'
        '- Set passed=false only for "poor" quality or policy_violations present\n'
    )


# ---------------------------------------------------------------------------
# Writer Agent – improve existing Issue (Task 3)
# ---------------------------------------------------------------------------


def improve_issue_prompt(existing_issue: dict) -> str:
    title = existing_issue.get("title", "")
    body = (existing_issue.get("body") or "")[:2500]
    labels = [lbl.get("name", "") for lbl in existing_issue.get("labels", [])]
    return (
        "You are the Writer Agent improving an existing GitHub Issue.\n"
        "Rewrite it to be clearer, more specific, and more actionable.\n\n"
        f"EXISTING TITLE: {title}\n"
        f"EXISTING LABELS: {labels}\n\n"
        f"EXISTING BODY:\n{body}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "title": "improved title — specific and actionable",\n'
        '  "problem_description": "improved problem description — remove vague language",\n'
        '  "evidence": "evidence section — specific files/patterns referenced",\n'
        '  "acceptance_criteria": ["specific testable criterion 1", "criterion 2"],\n'
        '  "risk_level": "low|medium|high",\n'
        '  "labels": ["suggested labels"]\n'
        "}\n\n"
        "Rules:\n"
        "- Remove vague words: 'various', 'some', 'stuff', 'things', 'etc.'\n"
        "- Add specific acceptance criteria if missing or non-testable\n"
        "- Keep the essence of the original; improve the structure and specificity\n"
        "- Do not invent new technical content not implied by the original\n"
    )


# ---------------------------------------------------------------------------
# Writer Agent – improve existing PR (Task 3)
# ---------------------------------------------------------------------------


def improve_pr_prompt(existing_pr: dict) -> str:
    title = existing_pr.get("title", "")
    body = (existing_pr.get("body") or "")[:2500]
    base_ref = existing_pr.get("base", {}).get("ref", "")
    head_ref = existing_pr.get("head", {}).get("ref", "")
    return (
        "You are the Writer Agent improving an existing GitHub Pull Request description.\n"
        "Rewrite it to be clearer, more complete, and more useful for reviewers.\n\n"
        f"EXISTING TITLE: {title}\n"
        f"BASE BRANCH: {base_ref}  HEAD BRANCH: {head_ref}\n\n"
        f"EXISTING BODY:\n{body}\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "title": "improved PR title (conventional commits style if appropriate)",\n'
        '  "summary": "clear summary of WHAT this PR does and WHY",\n'
        '  "files_affected": ["key files changed (infer from context if mentioned)"],\n'
        '  "behavior_change": "specific observable behavior changes",\n'
        '  "test_plan": "concrete actionable test steps",\n'
        '  "risk_level": "low|medium|high"\n'
        "}\n\n"
        "Rules:\n"
        "- Remove vague language: 'various', 'some changes', 'stuff', 'etc.'\n"
        "- Test plan must be actionable steps, not just 'run tests'\n"
        "- Behavior change must be specific and observable\n"
        "- Keep the essence of the original; improve structure and completeness\n"
    )

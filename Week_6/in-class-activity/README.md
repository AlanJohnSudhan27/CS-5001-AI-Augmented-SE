# GitHub Multi-Agent Assistant - n8n

This workflow turns the original n8n demo into a GitHub-focused assistant that can:

- review pull request code changes
- draft Issues and Pull Requests
- improve existing Issues and Pull Requests
- require explicit human approval before publishing changes back to GitHub

The workflow uses a webhook, a preparation node that gathers GitHub context, a `Verifier` assistant first, then `Analyzer`, `Reviewer`, `Artifact Decision`, issue/PR drafter, `Editor`, a routing node that chooses Issue vs PR, a draft builder, and a publish gate.

It also has two entry paths:

- automatic: the webhook path for GitHub-driven runs
- manual: a `Manual Trigger` plus `Manual Request Defaults` node so you can click `Execute workflow` in n8n without sending a request body

It also has a loop guard:

- blocks runs triggered by bot senders or automation-like accounts
- blocks artifacts that already contain the marker `<!-- generated-by-n8n-github-assistant -->`

## Workflow modes

The webhook accepts these `action` values:

- `no_action`
- `gather_evidence`
- `review_changes`
- `draft_issue`
- `draft_pr`
- `improve_issue`
- `improve_pr`

Behavior:

- `gather_evidence` returns files affected, behavior change, and risk level so you can choose `draft_issue` or `draft_pr` explicitly.
- Issue vs PR is a human choice. Select `draft_issue` or `draft_pr` explicitly.
- `draft_issue` and `draft_pr` require `confirm_artifact=true` to proceed. Without it, the workflow returns evidence and stops so you can decide first.
- `no_action` returns evidence (if provided) and stops.
- `review_changes` never publishes. It returns a review package with findings and a suggested PR comment.
- `draft_issue`, `draft_pr`, `improve_issue`, and `improve_pr` return a draft by default.
- verification happens before drafting or publishing, and blocked verification stops the workflow from proceeding
- loop-guard verification happens before drafting or publishing, so bot-authored events are stopped early
- Publishing only happens when `approve_publish=true` and a GitHub token is available.
- For `gather_evidence` runs with `approve_publish=false`, the verifier skips the LLM call to avoid n8n node timeouts on slower machines.
- For `gather_evidence`, the analyzer/reviewer also skip LLM calls by default and compute evidence deterministically (files changed + basic risk heuristic). Use `review_changes` if you want the slower, model-based review output.

## Setup

### 1. Start Ollama

Use the Windows Ollama service or another Ollama instance reachable by n8n.

Required model:

```bash
ollama pull qwen2.5:7b
```

Default Ollama URL used by the workflow:

```text
http://127.0.0.1:11434
```

### 2. Start n8n

PowerShell:

```powershell
npx n8n start
```

Open `http://localhost:5678`.

### 3. Import the workflow

1. Create a new workflow.
2. Import [workflow.json](/c:/Users/alanj/Desktop/CS5001-AI_Augemented_SWE/CS-5001-AI-Augmented-SE/Week_6/demo-0-code-review-n8n/workflow.json).
3. Save it.
4. Activate it if you want to use the production webhook URL.

## Webhook

Production URL:

```text
POST /webhook/github-assistant
```

UI URL (browser):

```text
GET /webhook/github-assistant-ui?repo_owner=OWNER&repo_name=REPO&head=BRANCH
```

The UI endpoint runs `gather_evidence` and shows the evidence plus 3 buttons:

- Draft Issue
- Draft PR
- No Action

Test URL:

```text
POST /webhook-test/github-assistant
```

## Manual Run

For a manual run inside n8n:

1. Open the workflow canvas.
2. Open the `Manual Request Defaults` node.
3. Edit the default fields there if needed.
4. Click `Execute workflow`.

This path does not require `Invoke-RestMethod` or a JSON body.

## Auth

For draft-only runs, a GitHub token is optional.

For publish runs, provide one of these:

- request body field: `github_token`

The token must be valid and have repository write access. A `401` means the token is invalid, expired, revoked, or missing the required permissions.

The workflow never returns the token in webhook responses, but it will still be stored in n8n execution data if you pass it in.

## Example payloads

### Gather evidence for a decision (human chooses Issue vs PR)

```json
{
  "action": "gather_evidence",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "pr_number": 42
}
```

You can also target a branch/ref, a commit, or a commit range:

If you omit `pr_number`, `commit`, and `head`, the workflow defaults to the latest change on the repo default branch (usually `main`) by using `base: <default_branch>~1` and `head: <default_branch>`.

```json
{
  "action": "gather_evidence",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "base": "main",
  "head": "feature/auth-retry"
}
```

```json
{
  "action": "gather_evidence",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "commit": "0123456789abcdef0123456789abcdef01234567"
}
```

```json
{
  "action": "gather_evidence",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "from": "a1b2c3d4",
  "to": "e5f6a7b8"
}
```

### Review a pull request

```json
{
  "action": "review_changes",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "pr_number": 42
}
```

### Draft an issue

```json
{
  "action": "draft_issue",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "confirm_artifact": true,
  "title": "Intermittent login timeout",
  "problem_statement": "Users sometimes hit a timeout during login.",
  "context": "Seen in production after a recent auth change.",
  "acceptance_criteria": [
    "Root cause identified",
    "Fix deployed",
    "Regression coverage added"
  ],
  "labels": ["bug", "triage"]
}
```

### Draft a pull request

```json
{
  "action": "draft_pr",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "confirm_artifact": true,
  "title": "Add retry handling to auth client",
  "summary": "Mitigates intermittent login timeout failures.",
  "context": "Implements bounded retries and adds tests.",
  "base": "main",
  "head": "feature/auth-retry",
  "linked_issues": [123]
}
```

### Improve an existing issue

```json
{
  "action": "improve_issue",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "issue_number": 123,
  "user_request": "Tighten the title, add acceptance criteria, and make the body easier for an engineer to act on."
}
```

### Improve an existing pull request

```json
{
  "action": "improve_pr",
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "pr_number": 42,
  "user_request": "Improve the PR description for reviewers and call out testing and rollout risk."
}
```

### Publish after approval

Use the same payload, add:

```json
{
  "approve_publish": true,
  "github_token": "ghp_your_token_here"
}
```

## PowerShell examples

You only need these when calling the webhook directly. For manual runs in n8n, use `Execute workflow` with the `Manual Request Defaults` node instead.

Draft an issue without publishing:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5678/webhook/github-assistant `
  -ContentType "application/json" `
  -Body '{
    "action":"draft_issue",
    "repo_owner":"octocat",
    "repo_name":"Hello-World",
    "title":"Intermittent login timeout",
    "problem_statement":"Users sometimes hit a timeout during login.",
    "context":"Seen in production after a recent auth change.",
    "labels":["bug","triage"]
  }' | ConvertTo-Json -Depth 10
```

Review a PR:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5678/webhook/github-assistant `
  -ContentType "application/json" `
  -Body '{
    "action":"review_changes",
    "repo_owner":"octocat",
    "repo_name":"Hello-World",
    "pr_number":42
  }' | ConvertTo-Json -Depth 10
```

Gather evidence for your Issue vs PR decision:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5678/webhook/github-assistant `
  -ContentType "application/json" `
  -Body '{
    "action":"gather_evidence",
    "repo_owner":"octocat",
    "repo_name":"Hello-World",
    "base":"main",
    "head":"feature/auth-retry"
  }' | ConvertTo-Json -Depth 10
```

Decide issue vs PR:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5678/webhook/github-assistant `
  -ContentType "application/json" `
  -Body '{
    "action":"draft_issue",
    "repo_owner":"octocat",
    "repo_name":"Hello-World",
    "title":"Login retry handling",
    "problem_statement":"Users see intermittent login timeouts after the auth client change.",
    "context":"We likely know the fix and want an issue drafted with clear next steps."
  }' | ConvertTo-Json -Depth 10
```

## Notes

- Re-import the workflow after changing [workflow.json](/c:/Users/alanj/Desktop/CS5001-AI_Augemented_SWE/CS-5001-AI-Augmented-SE/Week_6/demo-0-code-review-n8n/workflow.json).
- If Ollama is offline, one of the assistant nodes will fail.
- `draft_pr` publishing requires a non-empty `head` branch.
- The workflow currently drafts review comments for PR review but does not post inline review comments automatically.

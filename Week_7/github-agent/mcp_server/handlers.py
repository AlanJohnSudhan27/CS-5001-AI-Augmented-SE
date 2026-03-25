"""
Tool handlers — pure Python functions, one per tool.

Function names must match the tool names in schemas.py exactly;
app.py dispatches by name using getattr(handlers, name).

No MCP imports here — these are plain functions that can be
tested independently of the MCP server.
"""
import json
import subprocess
from pathlib import Path

import httpx

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GITHUB_TOKEN

MAX_FILE_CHARS = 8_000

# ---------------------------------------------------------------------------
# Git tools
# ---------------------------------------------------------------------------


def git_diff(repo_path: str, commit_range: str = "") -> str:
    # Check if the repo has any commits at all
    has_commits = subprocess.run(
        ["git", "-C", repo_path, "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if has_commits.returncode != 0:
        return "(no commits yet — this repository has no commit history to diff)"

    cmd = ["git", "-C", repo_path, "diff"]
    if commit_range:
        cmd.append(commit_range)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout.strip()

    # If no range was given and working tree diff is empty, fall back to the last commit
    if not commit_range and not output:
        # Count available commits (may be only the initial commit)
        count_result = subprocess.run(
            ["git", "-C", repo_path, "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        total = int(count_result.stdout.strip()) if count_result.returncode == 0 else 1

        if total <= 1:
            # Only the initial commit — diff it against an empty tree
            fallback = subprocess.run(
                ["git", "-C", repo_path, "diff", "4b825dc642cb6eb9a060e54bf899d15f3f762a07", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
        else:
            fallback = subprocess.run(
                ["git", "-C", repo_path, "diff", "HEAD~1..HEAD"],
                capture_output=True, text=True, timeout=30,
            )
        output = fallback.stdout.strip()
        if not output:
            return "(no changes in working tree or last commit)"
        # Prepend a note so downstream agents know this is a fallback diff
        header = "[NOTE: No uncommitted changes found. Showing diff from the last commit.]\n\n"
        return header + output[:MAX_FILE_CHARS]

    return output[:MAX_FILE_CHARS] if output else "(no changes)"


def git_log(repo_path: str, max_count: int = 10) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "log", f"--max-count={max_count}",
         "--pretty=format:%h %s (%an, %ar)"],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip() or "(no commits)"


def git_show(repo_path: str, commit_sha: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "show", commit_sha],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout.strip()
    return output[:MAX_FILE_CHARS] if output else f"Commit {commit_sha} not found."

# ---------------------------------------------------------------------------
# File tools
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    return Path(path).read_text(errors="replace")[:MAX_FILE_CHARS]


def list_directory(path: str) -> str:
    entries = sorted(Path(path).iterdir(), key=lambda e: (e.is_file(), e.name))
    lines = [f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries]
    return "\n".join(lines) or "(empty)"


def grep_code(pattern: str, path: str) -> str:
    result = subprocess.run(
        ["grep", "-rH", "-n", pattern, path],
        capture_output=True, text=True, timeout=15,
    )
    return result.stdout.strip()[:MAX_FILE_CHARS] or "No matches found."

# ---------------------------------------------------------------------------
# GitHub API tools
# ---------------------------------------------------------------------------

def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def github_get_issue(owner: str, repo: str, issue_number: int) -> str:
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}",
        headers=_github_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return json.dumps({
        "number": data["number"],
        "title": data["title"],
        "state": data["state"],
        "body": (data.get("body") or "")[:MAX_FILE_CHARS],
        "labels": [l["name"] for l in data.get("labels", [])],
        "url": data["html_url"],
    }, indent=2)


def github_get_pr(owner: str, repo: str, pr_number: int) -> str:
    resp = httpx.get(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_github_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return json.dumps({
        "number": data["number"],
        "title": data["title"],
        "state": data["state"],
        "body": (data.get("body") or "")[:MAX_FILE_CHARS],
        "head": data["head"]["ref"],
        "base": data["base"]["ref"],
        "url": data["html_url"],
        "changed_files": data.get("changed_files", 0),
    }, indent=2)


def github_create_issue(
    owner: str, repo: str, title: str, body: str, labels: list[str] | None = None
) -> str:
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    resp = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/issues",
        headers=_github_headers(),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return json.dumps({
        "number": data["number"],
        "title": data["title"],
        "url": data["html_url"],
    }, indent=2)


def github_create_pr(
    owner: str, repo: str, title: str, body: str, head: str, base: str
) -> str:
    payload = {"title": title, "body": body, "head": head, "base": base}
    resp = httpx.post(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        headers=_github_headers(),
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return json.dumps({
        "number": data["number"],
        "title": data["title"],
        "url": data["html_url"],
    }, indent=2)

"""
Web Server — thin FastAPI layer that proxies to the Orchestrator Agent.

Serves the static frontend, provides REST endpoints that forward to
the Orchestrator via A2A, and streams progress via WebSocket.
"""
from __future__ import annotations

import json
import re
import uuid

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import WEB_PORT, ORCHESTRATOR_PORT, MCP_PORT
from web.models import ReviewRequest, DraftRequest, ImproveRequest

app = FastAPI(title="GitHub Repository Agent")

ORCHESTRATOR_URL = f"http://localhost:{ORCHESTRATOR_PORT}"
MCP_URL = f"http://localhost:{MCP_PORT}"

# ---------------------------------------------------------------------------
# Repo URL helpers
# ---------------------------------------------------------------------------

_GITHUB_URL_RE = re.compile(
    r"(?:https?://)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.\s]+)"
)


def _parse_github_url(source: str) -> dict | None:
    """If source looks like a GitHub URL, return {owner, repo, url}."""
    m = _GITHUB_URL_RE.search(source.strip())
    if m:
        owner, repo = m.group("owner"), m.group("repo")
        url = f"https://github.com/{owner}/{repo}.git"
        return {"owner": owner, "repo": repo, "url": url}
    return None


async def _resolve_repo(source: str) -> tuple[str, str, str]:
    """Resolve a repo source to (local_path, owner, repo).

    If source is a URL, clone it via MCP and extract owner/repo.
    If local path, return it as-is with empty owner/repo.
    """
    parsed = _parse_github_url(source)
    if not parsed:
        return source, "", ""

    # Clone via MCP tool
    from mcp_client.session import MCPSession
    async with MCPSession(f"http://localhost:{MCP_PORT}/sse") as session:
        local_path = await session.call_tool("git_clone", repo_url=parsed["url"])

    return local_path, parsed["owner"], parsed["repo"]


# ---------------------------------------------------------------------------
# WebSocket connections for real-time updates
# ---------------------------------------------------------------------------

connected_clients: list[WebSocket] = []


async def broadcast(message: dict) -> None:
    for ws in connected_clients[:]:
        try:
            await ws.send_json(message)
        except Exception:
            connected_clients.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(ws)


# ---------------------------------------------------------------------------
# Helper — send task to Orchestrator via A2A
# ---------------------------------------------------------------------------

async def _send_to_orchestrator(message: dict) -> dict:
    payload = {
        "task_id": str(uuid.uuid4())[:8],
        "message": json.dumps(message),
        "context": "",
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/tasks/send", json=payload
        )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Task 1: Review Changes
# ---------------------------------------------------------------------------

@app.post("/api/review")
async def review_changes(req: ReviewRequest) -> dict:
    await broadcast({"event": "pipeline_start", "pipeline": "review"})

    repo_path, owner, repo = await _resolve_repo(req.repo_source)

    message = {
        "type": "review",
        "repo_path": repo_path,
        "commit_range": req.commit_range,
    }
    result = await _send_to_orchestrator(message)

    # Attach resolved info so the frontend can auto-fill GitHub fields
    result["_resolved"] = {"repo_path": repo_path, "owner": owner, "repo": repo}

    await broadcast({"event": "pipeline_complete", "pipeline": "review"})
    return result


# ---------------------------------------------------------------------------
# Task 2: Draft Issue/PR
# ---------------------------------------------------------------------------

@app.post("/api/draft")
async def draft_content(req: DraftRequest) -> dict:
    await broadcast({"event": "pipeline_start", "pipeline": "draft"})

    repo_path, url_owner, url_repo = await _resolve_repo(req.repo_source)

    message = {
        "type": "draft",
        "mode": req.mode,
        "action_type": req.action_type,
        "repo_path": repo_path,
        "commit_range": req.commit_range,
        "instruction": req.instruction,
        "review_context": req.review_context,
        "owner": req.owner or url_owner,
        "repo": req.repo or url_repo,
        "head": req.head,
        "base": req.base,
    }
    result = await _send_to_orchestrator(message)

    await broadcast({"event": "pipeline_complete", "pipeline": "draft"})
    return result


# ---------------------------------------------------------------------------
# Task 3: Improve Issue/PR
# ---------------------------------------------------------------------------

@app.post("/api/improve")
async def improve_content(req: ImproveRequest) -> dict:
    await broadcast({"event": "pipeline_start", "pipeline": "improve"})

    # Extract owner/repo from URL or "owner/repo" string
    parsed = _parse_github_url(req.repo_source)
    if parsed:
        owner, repo = parsed["owner"], parsed["repo"]
    elif "/" in req.repo_source:
        # Treat as "owner/repo" format
        parts = req.repo_source.strip().split("/")
        owner, repo = parts[0], parts[1]
    else:
        owner, repo = "", ""

    if req.item_type == "pr":
        message = {
            "type": "improve_pr",
            "owner": owner,
            "repo": repo,
            "pr_number": req.number,
        }
    else:
        message = {
            "type": "improve_issue",
            "owner": owner,
            "repo": repo,
            "issue_number": req.number,
        }
    result = await _send_to_orchestrator(message)

    await broadcast({"event": "pipeline_complete", "pipeline": "improve"})
    return result


# ---------------------------------------------------------------------------
# Approval endpoints — proxy to Orchestrator
# ---------------------------------------------------------------------------

@app.post("/api/approve/{task_id}")
async def approve(task_id: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{ORCHESTRATOR_URL}/tasks/approve/{task_id}")
    resp.raise_for_status()
    result = resp.json()
    await broadcast({"event": "approved", "task_id": task_id, "result": result})
    return result


@app.post("/api/reject/{task_id}")
async def reject(task_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{ORCHESTRATOR_URL}/tasks/reject/{task_id}")
    resp.raise_for_status()
    result = resp.json()
    await broadcast({"event": "rejected", "task_id": task_id})
    return result


# ---------------------------------------------------------------------------
# Static files — serve frontend
# ---------------------------------------------------------------------------

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print(f"Web server on http://localhost:{WEB_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)

"""
Orchestrator Agent — discovers worker agents and runs pipelines.

Skills: orchestration, pipeline_management, agent_discovery

This is the central A2A agent. The web server only talks to the
Orchestrator, which then coordinates the 4 worker agents:
  Reviewer → Planner → Writer → Gatekeeper

It also manages the human-approval gate: drafts are held in memory
until the web server relays an approve or reject from the user.
"""
from __future__ import annotations

import json
import uuid

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from agents.base import BaseA2AAgent, Task, TaskResult, AgentCard
from config import (
    ORCHESTRATOR_PORT, REVIEWER_PORT, PLANNER_PORT,
    WRITER_PORT, GATEKEEPER_PORT, MCP_PORT,
)


WORKER_ENDPOINTS = [
    f"http://localhost:{REVIEWER_PORT}",
    f"http://localhost:{PLANNER_PORT}",
    f"http://localhost:{WRITER_PORT}",
    f"http://localhost:{GATEKEEPER_PORT}",
]


class ApprovalRequest(BaseModel):
    action: str  # "approve" or "reject"


class OrchestratorAgent(BaseA2AAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Orchestrator",
            description="Discovers worker agents and orchestrates review/draft/improve pipelines.",
            skills=["orchestration", "pipeline_management", "agent_discovery"],
            port=ORCHESTRATOR_PORT,
            mcp_url=f"http://localhost:{MCP_PORT}/sse",
        )
        self.workers: list[dict] = []
        self.pending_approvals: dict[str, dict] = {}
        self._register_extra_routes()

    # ------------------------------------------------------------------
    # Extra routes for approval flow
    # ------------------------------------------------------------------

    def _register_extra_routes(self) -> None:
        agent = self

        @self.app.post("/tasks/approve/{task_id}")
        async def approve_task(task_id: str) -> dict:
            return await agent._handle_approval(task_id, approved=True)

        @self.app.post("/tasks/reject/{task_id}")
        async def reject_task(task_id: str) -> dict:
            return await agent._handle_approval(task_id, approved=False)

        @self.app.get("/tasks/pending")
        async def list_pending() -> list[dict]:
            return [
                {"task_id": tid, "type": data.get("type", "unknown")}
                for tid, data in agent.pending_approvals.items()
            ]

    # ------------------------------------------------------------------
    # Agent discovery (A2A pattern)
    # ------------------------------------------------------------------

    async def discover_workers(self) -> list[dict]:
        self.workers = []
        async with httpx.AsyncClient(timeout=5) as client:
            for endpoint in WORKER_ENDPOINTS:
                try:
                    resp = await client.get(f"{endpoint}/.well-known/agent.json")
                    resp.raise_for_status()
                    card = resp.json()
                    card["endpoint"] = endpoint
                    self.workers.append(card)
                except Exception:
                    pass
        return self.workers

    def _get_worker(self, name: str) -> dict | None:
        return next((w for w in self.workers if w["name"] == name), None)

    # ------------------------------------------------------------------
    # A2A task delegation
    # ------------------------------------------------------------------

    async def _send_to_worker(
        self, worker_name: str, message: str, context: str = ""
    ) -> dict:
        worker = self._get_worker(worker_name)
        if not worker:
            return {"status": "failed", "output": f"Worker {worker_name} not found"}

        payload = {
            "task_id": str(uuid.uuid4())[:8],
            "message": message,
            "context": context,
        }
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{worker['endpoint']}/tasks/send", json=payload
            )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Main handler — routes to the correct pipeline
    # ------------------------------------------------------------------

    async def handle(self, task: Task) -> str:
        # Discover workers on first request
        if not self.workers:
            await self.discover_workers()

        try:
            request = json.loads(task.message)
        except json.JSONDecodeError:
            request = {"type": "review", "repo_path": task.message}

        pipeline_type = request.get("type", "review")

        if pipeline_type == "review":
            return await self._run_review_pipeline(request)
        elif pipeline_type == "draft":
            return await self._run_draft_pipeline(request)
        elif pipeline_type in ("improve_issue", "improve_pr"):
            return await self._run_improve_pipeline(request)
        else:
            return json.dumps({"error": f"Unknown pipeline type: {pipeline_type}"})

    # ------------------------------------------------------------------
    # Pipeline: Review Changes (Task 1)
    # ------------------------------------------------------------------

    async def _run_review_pipeline(self, request: dict) -> str:
        stages = {}

        # Stage 1: Reviewer analyzes changes
        reviewer_result = await self._send_to_worker(
            "Reviewer", json.dumps(request)
        )
        stages["reviewer"] = reviewer_result.get("output", "")

        return json.dumps({
            "pipeline": "review",
            "stages": stages,
            "status": "completed",
        })

    # ------------------------------------------------------------------
    # Pipeline: Draft Issue/PR (Task 2)
    # ------------------------------------------------------------------

    async def _run_draft_pipeline(self, request: dict) -> str:
        stages = {}
        task_id = str(uuid.uuid4())[:8]

        # Determine mode
        mode = request.get("mode", "from_instruction")
        repo_path = request.get("repo_path", ".")
        instruction = request.get("instruction", "")
        commit_range = request.get("commit_range", "")

        # Stage 1: Reviewer
        if mode == "from_instruction":
            review_request = {
                "type": "review",
                "repo_path": repo_path,
                "commit_range": commit_range,
            }
            reviewer_result = await self._send_to_worker(
                "Reviewer", json.dumps(review_request)
            )
            stages["reviewer"] = reviewer_result.get("output", "")
        else:
            # from_review: use provided review context
            stages["reviewer"] = request.get("review_context", "")

        # Stage 2: Planner
        planner_request = {
            "action_type": request.get("action_type", "auto"),
            "instruction": instruction,
        }
        planner_result = await self._send_to_worker(
            "Planner",
            json.dumps(planner_request),
            context=stages["reviewer"],
        )
        stages["planner"] = planner_result.get("output", "")

        # Stage 3: Writer
        action_type = request.get("action_type", "issue")
        writer_request = {"action_type": action_type}
        writer_result = await self._send_to_worker(
            "Writer",
            json.dumps(writer_request),
            context=stages["planner"],
        )
        stages["writer"] = writer_result.get("output", "")

        # Stage 4: Gatekeeper (reflection)
        gatekeeper_result = await self._send_to_worker(
            "Gatekeeper",
            stages["writer"],
            context=f"REVIEW:\n{stages['reviewer']}\n\nPLAN:\n{stages['planner']}",
        )
        stages["gatekeeper"] = gatekeeper_result.get("output", "")

        # Store for approval
        self.pending_approvals[task_id] = {
            "type": "draft",
            "action_type": action_type,
            "request": request,
            "stages": stages,
        }

        return json.dumps({
            "pipeline": "draft",
            "task_id": task_id,
            "stages": stages,
            "status": "awaiting_approval",
        })

    # ------------------------------------------------------------------
    # Pipeline: Improve Issue/PR (Task 3)
    # ------------------------------------------------------------------

    async def _run_improve_pipeline(self, request: dict) -> str:
        stages = {}
        task_id = str(uuid.uuid4())[:8]
        pipeline_type = request.get("type", "improve_issue")

        # Stage 1: Reviewer critiques existing content
        reviewer_result = await self._send_to_worker(
            "Reviewer", json.dumps(request)
        )
        stages["reviewer"] = reviewer_result.get("output", "")

        # Stage 2: Planner plans improvements
        planner_request = {"action_type": pipeline_type}
        planner_result = await self._send_to_worker(
            "Planner",
            json.dumps(planner_request),
            context=stages["reviewer"],
        )
        stages["planner"] = planner_result.get("output", "")

        # Stage 3: Writer produces improved version
        writer_request = {"action_type": pipeline_type}
        writer_result = await self._send_to_worker(
            "Writer",
            json.dumps(writer_request),
            context=f"PLAN:\n{stages['planner']}\n\nORIGINAL CRITIQUE:\n{stages['reviewer']}",
        )
        stages["writer"] = writer_result.get("output", "")

        # Stage 4: Gatekeeper reflection
        gatekeeper_result = await self._send_to_worker(
            "Gatekeeper",
            stages["writer"],
            context=f"CRITIQUE:\n{stages['reviewer']}\n\nPLAN:\n{stages['planner']}",
        )
        stages["gatekeeper"] = gatekeeper_result.get("output", "")

        # Store for approval
        self.pending_approvals[task_id] = {
            "type": pipeline_type,
            "request": request,
            "stages": stages,
        }

        return json.dumps({
            "pipeline": pipeline_type,
            "task_id": task_id,
            "stages": stages,
            "status": "awaiting_approval",
        })

    # ------------------------------------------------------------------
    # Approval handling
    # ------------------------------------------------------------------

    async def _handle_approval(self, task_id: str, approved: bool) -> dict:
        pending = self.pending_approvals.pop(task_id, None)
        if not pending:
            return {"status": "error", "message": f"No pending task {task_id}"}

        if not approved:
            return {"status": "rejected", "task_id": task_id}

        # Execute the GitHub action via MCP
        try:
            writer_output = pending["stages"].get("writer", "{}")
            try:
                draft = json.loads(writer_output)
            except json.JSONDecodeError:
                draft = {"title": "Untitled", "body": writer_output}

            request = pending.get("request", {})
            action_type = pending.get("action_type", pending.get("type", "issue"))

            owner = request.get("owner", "")
            repo = request.get("repo", "")

            if action_type in ("issue", "draft") and owner and repo:
                result = await self.mcp_call(
                    "github_create_issue",
                    owner=owner,
                    repo=repo,
                    title=draft.get("title", "Untitled"),
                    body=draft.get("body", ""),
                )
                return {"status": "approved", "task_id": task_id, "result": result}

            elif action_type == "pr" and owner and repo:
                result = await self.mcp_call(
                    "github_create_pr",
                    owner=owner,
                    repo=repo,
                    title=draft.get("title", "Untitled"),
                    body=draft.get("body", ""),
                    head=request.get("head", "main"),
                    base=request.get("base", "main"),
                )
                return {"status": "approved", "task_id": task_id, "result": result}

            else:
                return {
                    "status": "approved",
                    "task_id": task_id,
                    "message": "Draft approved but no GitHub target configured.",
                    "draft": draft,
                }

        except Exception as exc:
            return {"status": "error", "task_id": task_id, "message": str(exc)}

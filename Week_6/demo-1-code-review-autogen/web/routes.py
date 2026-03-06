"""
API routes for Code Review AutoGen web UI.

Endpoints:
  POST /api/review           — start a pipeline run, returns {job_id}
  GET  /api/stream/{job_id}  — SSE stream of pipeline events
  GET  /api/last             — return the last saved report as JSON
  GET  /api/browse?path=...  — directory listing for the file picker
"""
import asyncio
import json
import pathlib
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from pipeline import load_last_report, run_pipeline
from web.jobs import create_job, emit, get_queue, remove_job

router = APIRouter()

_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".swift",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
}


# ── Request model ───────────────────────────────────────────────

class ReviewRequest(BaseModel):
    path: str


# ── POST /api/review ────────────────────────────────────────────

@router.post("/review")
async def start_review(req: ReviewRequest):
    job_id = create_job()
    asyncio.create_task(_run_pipeline(job_id, req.path))
    return {"job_id": job_id}


async def _run_pipeline(job_id: str, path: str) -> None:
    """
    Run the AutoGen pipeline as a background task, forwarding
    each emit() call to the SSE queue for this job.

    Since run_pipeline is already async (AutoGen uses async/await),
    we call it directly — no thread pool needed unlike the Ollama version.
    """
    current_agent_state: dict = {"current": None}

    async def tracked_emit(agent: str, message: str) -> None:
        agent_order = ["Analyzer", "Reviewer", "Suggester", "Summarizer"]
        if agent != current_agent_state["current"] and agent in agent_order:
            await emit(job_id, {"type": "agent_start", "agent": agent})
            current_agent_state["current"] = agent

        is_tool = message.startswith("[tool]")
        await emit(job_id, {
            "type": "log",
            "agent": agent,
            "message": message,
            "is_tool": is_tool,
        })

    try:
        report = await run_pipeline(path, emit=tracked_emit)
        await emit(job_id, {"type": "agent_done", "agent": "Summarizer"})
        await emit(job_id, {"type": "done", "report": report})
    except Exception as exc:
        await emit(job_id, {"type": "error", "message": str(exc)})


# ── GET /api/stream/{job_id} ────────────────────────────────────

@router.get("/stream/{job_id}")
async def stream(job_id: str):
    return StreamingResponse(
        _event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _event_generator(job_id: str) -> AsyncGenerator[str, None]:
    q = get_queue(job_id)
    if q is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
        return
    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=300.0)
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout'})}\n\n"
            break
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") in ("done", "error"):
            remove_job(job_id)
            break


# ── GET /api/last ───────────────────────────────────────────────

@router.get("/last")
async def get_last_report():
    report = load_last_report()
    if report is None:
        return JSONResponse({"error": "No report saved yet."}, status_code=404)
    return report


# ── GET /api/browse ─────────────────────────────────────────────

@router.get("/browse")
async def browse(path: str = Query(default="~")):
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            p = Path.home()
        if p.is_file():
            p = p.parent

        entries = []
        try:
            for item in sorted(p.iterdir()):
                if item.name.startswith(".") or item.name in ("__pycache__", "node_modules"):
                    continue
                if item.is_dir():
                    entries.append({"name": item.name, "type": "dir", "path": str(item)})
                elif item.is_file() and item.suffix in _SOURCE_EXTS:
                    entries.append({"name": item.name, "type": "file", "path": str(item)})
        except PermissionError:
            pass

        parent = str(p.parent) if p != p.parent else None
        return {"path": str(p), "parent": parent, "entries": entries}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

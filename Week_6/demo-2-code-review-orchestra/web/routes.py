"""
API routes for Code Review Orchestra web UI.

Endpoints:
  POST /api/review           — start a pipeline run, returns {job_id}
  GET  /api/stream/{id}      — SSE stream of pipeline events for a job
  GET  /api/last             — return the last saved report as JSON
  GET  /api/browse?path=...  — list directory contents for the file picker
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

from orchestrator import Orchestrator, load_last_report
from web.jobs import create_job, emit, get_queue, remove_job

router = APIRouter()

# Source extensions shown in the file browser
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".swift",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
}

# ── Request / response models ──────────────────────────────────

class ReviewRequest(BaseModel):
    path: str
    parallel: bool = False


# ── POST /api/review ───────────────────────────────────────────

@router.post("/review")
async def start_review(req: ReviewRequest):
    job_id = create_job()
    asyncio.create_task(_run_pipeline(job_id, req.path, req.parallel))
    return {"job_id": job_id}


async def _run_pipeline(job_id: str, path: str, parallel: bool) -> None:
    loop = asyncio.get_event_loop()
    current_agent_state: dict = {"current": None}

    def tracked_emit(agent: str, message: str) -> None:
        agent_order = ["Analyzer", "Reviewer", "Suggester", "Summarizer"]
        if agent != current_agent_state["current"] and agent in agent_order:
            asyncio.run_coroutine_threadsafe(
                emit(job_id, {"type": "agent_start", "agent": agent}),
                loop,
            )
            current_agent_state["current"] = agent

        is_tool = message.startswith("[tool]")
        asyncio.run_coroutine_threadsafe(
            emit(job_id, {
                "type": "log",
                "agent": agent,
                "message": message,
                "is_tool": is_tool,
            }),
            loop,
        )

    try:
        orchestrator = Orchestrator()
        report = await orchestrator.run_async(path, parallel=parallel, emit=tracked_emit)
        await emit(job_id, {"type": "agent_done", "agent": "Summarizer"})
        await emit(job_id, {"type": "done", "report": report.to_dict()})
    except Exception as exc:
        await emit(job_id, {"type": "error", "message": str(exc)})


# ── GET /api/stream/{job_id} ───────────────────────────────────

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
            event = await asyncio.wait_for(q.get(), timeout=180.0)
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout'})}\n\n"
            break
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") in ("done", "error"):
            remove_job(job_id)
            break


# ── GET /api/last ──────────────────────────────────────────────

@router.get("/last")
async def get_last_report():
    report = load_last_report()
    if report is None:
        return JSONResponse({"error": "No report saved yet."}, status_code=404)
    return report.to_dict()


# ── GET /api/browse ────────────────────────────────────────────

@router.get("/browse")
async def browse(path: str = Query(default="~")):
    """
    List the contents of a directory for the web UI file picker.

    Returns:
      {
        "path": "/absolute/current/path",
        "parent": "/absolute/parent/path" | null,
        "entries": [
          {"name": "subdir", "type": "dir",  "path": "/absolute/path/subdir"},
          {"name": "file.py","type": "file", "path": "/absolute/path/file.py"}
        ]
      }
    """
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            # Fall back to home if path doesn't exist
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

        return {
            "path": str(p),
            "parent": parent,
            "entries": entries,
        }
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

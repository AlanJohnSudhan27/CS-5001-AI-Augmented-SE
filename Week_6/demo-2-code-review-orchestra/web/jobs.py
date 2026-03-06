"""
Job registry — one asyncio.Queue per in-flight pipeline run.

Pattern:
  1. POST /api/review → create_job() → returns job_id
  2. Background task calls emit(job_id, agent, message) to push events
  3. GET /api/stream/{job_id} → drains the queue via SSE
"""
import asyncio
import uuid
from typing import Optional

_jobs: dict[str, asyncio.Queue] = {}


def create_job() -> str:
    """Create a new job queue and return the job_id UUID."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = asyncio.Queue()
    return job_id


async def emit(job_id: str, event: dict) -> None:
    """Push a JSON-serialisable event dict to the job's queue."""
    q = _jobs.get(job_id)
    if q is not None:
        await q.put(event)


def get_queue(job_id: str) -> Optional[asyncio.Queue]:
    """Return the queue for job_id, or None if not found."""
    return _jobs.get(job_id)


def remove_job(job_id: str) -> None:
    """Remove the job from the registry after streaming is complete."""
    _jobs.pop(job_id, None)

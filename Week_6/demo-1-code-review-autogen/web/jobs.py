"""
Job registry — one asyncio.Queue per in-flight pipeline run.

Pattern:
  1. POST /api/review → create_job() → returns job_id
  2. Background coroutine calls emit(job_id, event_dict)
  3. GET /api/stream/{job_id} → drains the queue via SSE
"""
import asyncio
import uuid
from typing import Optional

_jobs: dict[str, asyncio.Queue] = {}


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = asyncio.Queue()
    return job_id


async def emit(job_id: str, event: dict) -> None:
    q = _jobs.get(job_id)
    if q is not None:
        await q.put(event)


def get_queue(job_id: str) -> Optional[asyncio.Queue]:
    return _jobs.get(job_id)


def remove_job(job_id: str) -> None:
    _jobs.pop(job_id, None)

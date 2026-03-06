"""
FastAPI application entry point for Code Review Orchestra web UI.

Run with:
  cd code-review-orchestra
  uvicorn web.main:app --reload --port 8001
"""
import pathlib
import sys

# Ensure the project root is importable
_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.routes import router

app = FastAPI(
    title="Code Review Orchestra",
    description="LLM Agent Orchestration Demo — CS 5001",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (JS, CSS — everything in web/static/)
_STATIC_DIR = _ROOT / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# API routes under /api prefix
app.include_router(router, prefix="/api")


@app.get("/")
async def index():
    """Serve the SPA index.html."""
    return FileResponse(str(_STATIC_DIR / "index.html"))

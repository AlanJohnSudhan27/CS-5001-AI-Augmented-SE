"""
FastAPI app for Code Review AutoGen web UI.

Run with:
  cd code-review-autogen
  uvicorn web.main:app --reload --port 8002
"""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.routes import router

app = FastAPI(
    title="Code Review AutoGen",
    description="AutoGen Multi-Agent Demo — CS 5001",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = _ROOT / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(router, prefix="/api")


@app.get("/")
async def index():
    return FileResponse(str(_STATIC_DIR / "index.html"))

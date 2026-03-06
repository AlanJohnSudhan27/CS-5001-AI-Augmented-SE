"""
Configuration — loaded from .env via python-dotenv.

Optional:
  OLLAMA_HOST   — defaults to http://localhost:11434
  AGENT_MODEL   — defaults to llama3.2:3b
  MAX_TOKENS    — max tokens to generate per LLM call, defaults to 2048
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL: str       = os.getenv("AGENT_MODEL", "llama3.2:3b")
MAX_TOKENS: int  = int(os.getenv("MAX_TOKENS", "2048"))

# Persist last report so `python cli.py last` can read it
REPORT_FILE: Path = Path(__file__).parent / ".last_report.json"

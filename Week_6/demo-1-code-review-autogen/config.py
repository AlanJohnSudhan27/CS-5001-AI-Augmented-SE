"""
Configuration — loaded from .env (falls back to sensible defaults).

Copy .env.example → .env and set OLLAMA_HOST / AGENT_MODEL if needed.
Better tool-calling models: llama3.1:8b, qwen2.5:7b, mistral:7b
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL: str = os.getenv("AGENT_MODEL", "llama3.2:3b")
REPORT_FILE: Path = Path(__file__).parent / ".last_report.json"

import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",  "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Auto-select provider: Groq if API key is set, otherwise Ollama
LLM_PROVIDER = "groq" if GROQ_API_KEY else "ollama"

MCP_PORT          = int(os.getenv("MCP_PORT", "8050"))
ORCHESTRATOR_PORT = int(os.getenv("ORCHESTRATOR_PORT", "8100"))
REVIEWER_PORT     = int(os.getenv("REVIEWER_PORT", "8101"))
PLANNER_PORT      = int(os.getenv("PLANNER_PORT", "8102"))
WRITER_PORT       = int(os.getenv("WRITER_PORT", "8103"))
GATEKEEPER_PORT   = int(os.getenv("GATEKEEPER_PORT", "8104"))
WEB_PORT          = int(os.getenv("WEB_PORT", "8000"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

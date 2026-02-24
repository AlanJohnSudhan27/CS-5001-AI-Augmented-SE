"""
config.py — LocalClaw Personal AI Gateway

Passwords and 2FA are NEVER stored here.
Hotmail auth is handled entirely by Microsoft's device flow (browser-based).
Token is cached in OS keychain automatically.
"""

# ── Identity ──────────────────────────────────────────────────────────────────
OWNER_NAME   = "Imran"                  # Your name — used in memory + personality
ASSISTANT_NAME = "LocalClaw"           # Assistant name shown in dashboard + replies

# ── Hotmail / Microsoft Graph ─────────────────────────────────────────────────
EMAIL_ADDRESS = "imranraad@live.co.uk"       # Your Hotmail / Outlook / Live address

# ── Ollama (local AI model) ───────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3.2:3b"             # any pulled model: mistral, phi3, gemma2…

# ── Gateway behaviour ─────────────────────────────────────────────────────────
POLL_INTERVAL     = 30                 # seconds between inbox checks
DRY_RUN           = True              # True = log replies, don't send
DELETE_AFTER_READ = False             # True = delete emails after processing

# ── Dashboard API ─────────────────────────────────────────────────────────────
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 5000
DASHBOARD_DEBUG = False

# ── Memory ────────────────────────────────────────────────────────────────────
MEMORY_FILE = "memory.json"           # where LocalClaw stores persistent memory
MAX_LOG_LINES = 200                   # max log lines kept in memory

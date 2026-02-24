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
EMAIL_ADDRESS = ""       # Your Hotmail / Outlook / Live address

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

# ── GitHub ────────────────────────────────────────────────────────────────────
# Get your PAT: https://github.com/settings/tokens/new  (scopes: notifications + repo)
# Paste it below OR leave blank — you will be prompted once and it will be cached in keychain.
GITHUB_TOKEN         = ""             # paste your GitHub Personal Access Token here
GITHUB_USERNAME      = ""  # your GitHub username
GITHUB_POLL_INTERVAL = 60             # seconds (GitHub recommends >= 60s)
GITHUB_AUTO_REPLY    = False          # True = post AI comments automatically
GITHUB_GATEWAY_HOST  = "127.0.0.1"
GITHUB_GATEWAY_PORT  = 5001
GITHUB_GATEWAY_DEBUG = False

# ── Canvas LMS ────────────────────────────────────────────────────────────────
# Get your token: Canvas → Account → Settings → scroll to "Approved Integrations" → New Access Token
# Paste it below OR leave blank — you will be prompted once and it will be cached in keychain.
CANVAS_TOKEN         = ""             # paste your Canvas API token here
CANVAS_BASE_URL      = ""  # your Canvas instance URL
CANVAS_POLL_INTERVAL = 60
CANVAS_AUTO_REPLY    = False          # True = post AI replies to conversations automatically
CANVAS_GATEWAY_HOST  = "127.0.0.1"
CANVAS_GATEWAY_PORT  = 5002
CANVAS_GATEWAY_DEBUG = False


"""
core/config.py
All configuration for the LocalClaw gateway.
Edit values here or override via CLI flags.
"""


class Config:
    # ── Guerrilla Mail ────────────────────────────────────────────────────────
    # Leave empty for a random disposable address.
    # Set a name like "myclaw" to always use myclaw@guerrillamailblock.com
    GUERRILLA_EMAIL_USER: str = "cs5001demo@guerrillamailblock.com"

    # ── Ollama ────────────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "llama3.2:3b"   # any pulled model: mistral, phi3, gemma2…

    # ── Gateway behaviour ─────────────────────────────────────────────────────
    POLL_INTERVAL:     int  = 30      # seconds between inbox checks
    DRY_RUN:           bool = True    # True = log replies, don't send/act
    DELETE_AFTER_READ: bool = False   # True = delete emails after processing
    MAX_BODY_CHARS:    int  = 3000    # truncate long email bodies sent to Ollama

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_FILE:  str  = "localclaw.log"
    LOG_LEVEL: str  = "INFO"

    # ── AI persona ────────────────────────────────────────────────────────────
    ASSISTANT_NAME: str = "LocalClaw"
    SYSTEM_PROMPT: str = (
        "You are LocalClaw, a helpful personal AI email assistant. "
        "Read incoming emails and write clear, concise, professional replies. "
        "Keep replies friendly and to the point. "
        "Sign off with: — LocalClaw (your AI assistant)"
    )

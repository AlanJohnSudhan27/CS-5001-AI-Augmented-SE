"""
memory.py — LocalClaw Persistent Memory & Personality

Stores and retrieves facts, conversation context, and stats
across sessions using a simple JSON file.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
import config

_lock = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> dict:
    path = Path(config.MEMORY_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return _default()


def _save(data: dict) -> None:
    Path(config.MEMORY_FILE).write_text(
        json.dumps(data, indent=2, ensure_ascii=False)
    )


def _default() -> dict:
    return {
        "identity": {
            "name":       config.ASSISTANT_NAME,
            "owner":      config.OWNER_NAME,
            "created_at": _now(),
            "tone":       "Professional, concise, warm",
            "sign_off":   f"— {config.ASSISTANT_NAME} (your AI assistant)",
            "model":      config.OLLAMA_MODEL,
        },
        "stats": {
            "emails_processed": 0,
            "replies_sent":     0,
            "emails_skipped":   0,
            "uptime_start":     _now(),
        },
        "memory": {},       # key → {value, updated_at}
        "senders": {},      # email → {name, last_seen, count, last_subject}
        "emails": [],       # last N emails processed (capped)
        "logs": [],         # live log ring buffer
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_all() -> dict:
    with _lock:
        return _load()


def remember(key: str, value: str) -> None:
    with _lock:
        data = _load()
        data["memory"][key] = {"value": value, "updated_at": _now()}
        _save(data)


def recall(key: str) -> str | None:
    with _lock:
        data = _load()
        entry = data["memory"].get(key)
        return entry["value"] if entry else None


def forget(key: str) -> None:
    with _lock:
        data = _load()
        data["memory"].pop(key, None)
        _save(data)


def increment_stat(key: str, by: int = 1) -> None:
    with _lock:
        data = _load()
        data["stats"][key] = data["stats"].get(key, 0) + by
        _save(data)


def get_stats() -> dict:
    with _lock:
        return _load()["stats"]


def record_sender(email: str, name: str, subject: str) -> None:
    with _lock:
        data = _load()
        sender = data["senders"].get(email, {"count": 0})
        sender.update({
            "name":         name,
            "last_seen":    _now(),
            "last_subject": subject,
            "count":        sender["count"] + 1,
        })
        data["senders"][email] = sender
        _save(data)


def get_senders() -> dict:
    with _lock:
        return _load()["senders"]


def record_email(email_dict: dict) -> None:
    """Save a processed email to memory (capped at 50)."""
    with _lock:
        data = _load()
        data["emails"].insert(0, {**email_dict, "recorded_at": _now()})
        data["emails"] = data["emails"][:50]
        _save(data)


def get_emails() -> list:
    with _lock:
        return _load()["emails"]


def add_log(level: str, message: str) -> None:
    with _lock:
        data = _load()
        data["logs"].insert(0, {
            "ts":      _now(),
            "level":   level,
            "message": message,
        })
        data["logs"] = data["logs"][:config.MAX_LOG_LINES]
        _save(data)


def get_logs(n: int = 50) -> list:
    with _lock:
        return _load()["logs"][:n]


def get_identity() -> dict:
    with _lock:
        return _load()["identity"]


def uptime_seconds() -> int:
    stats = get_stats()
    try:
        start = datetime.fromisoformat(stats["uptime_start"])
        return int((datetime.now() - start).total_seconds())
    except Exception:
        return 0


def build_system_prompt() -> str:
    identity = get_identity()
    mem      = _load()["memory"]
    sender_facts = ""
    if mem:
        facts = "\n".join(
            f"  - {k}: {v['value']}" for k, v in list(mem.items())[:10]
        )
        sender_facts = f"\nThings you remember:\n{facts}"

    return f"""You are {identity['name']}, a personal AI email assistant owned by {identity['owner']}.
Tone: {identity['tone']}.
Sign every reply with: {identity['sign_off']}
{sender_facts}
Read incoming emails carefully and write clear, helpful, professional replies.
Keep replies concise and relevant. Never mention that you are an AI unless asked."""

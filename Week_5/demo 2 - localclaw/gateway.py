"""
LocalClaw Personal AI Gateway
==============================
- Polls Hotmail inbox via Microsoft Graph API
- Generates replies using local Ollama model
- Persists memory across sessions
- Exposes a Flask REST API for the dashboard
- Runs cron jobs in background threads

Passwords and 2FA: handled by Microsoft device flow.
Token cached in OS keychain — never in code.
"""

import re
import time
import threading
import logging
import datetime
from logging.handlers import RotatingFileHandler

import requests
import keyring
from flask import Flask, jsonify, request
from flask_cors import CORS

import config
import memory as mem

# ── Logging ───────────────────────────────────────────────────────────────────

class MemoryLogHandler(logging.Handler):
    """Sends log records to the memory module's log buffer."""
    def emit(self, record):
        level = record.levelname.lower()
        if level == "warning": level = "warn"
        mem.add_log(level, self.format(record))

log = logging.getLogger("localclaw")
log.setLevel(logging.INFO)

fmt = logging.Formatter("%(message)s")

# File handler
fh = RotatingFileHandler("gateway.log", maxBytes=1_000_000, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(fh)

# Stream handler
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(sh)

# Memory handler (feeds dashboard)
mh = MemoryLogHandler()
mh.setFormatter(fmt)
log.addHandler(mh)


# ══════════════════════════════════════════════════════════════════════════════
# HOTMAIL BACKEND — Microsoft Graph OAuth2
# ══════════════════════════════════════════════════════════════════════════════

GRAPH_BASE  = "https://graph.microsoft.com/v1.0"
KEYRING_APP = "localclaw"


def keychain_get(key):
    return keyring.get_password(KEYRING_APP, key)


def keychain_set(key, value):
    keyring.set_password(KEYRING_APP, key, value)


def keychain_delete(key):
    try:
        keyring.delete_password(KEYRING_APP, key)
    except Exception:
        pass


class HotmailBackend:
    CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
    SCOPES    = ["Mail.Read", "Mail.ReadWrite", "Mail.Send", "User.Read"]

    def __init__(self, address: str):
        self.address    = address
        self._cache_key = f"hotmail_token_cache_{address}"
        self._token     = self._load_or_acquire_token()
        self._status    = "ok"

    def _load_or_acquire_token(self) -> str:
        import msal
        cache_json = keychain_get(self._cache_key)
        cache = msal.SerializableTokenCache()
        if cache_json:
            cache.deserialize(cache_json)

        app = msal.PublicClientApplication(
            self.CLIENT_ID,
            authority="https://login.microsoftonline.com/consumers",
            token_cache=cache,
        )

        accounts = app.get_accounts(username=self.address)
        if accounts:
            result = app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._persist(cache)
                log.info("Hotmail token refreshed silently.")
                return result["access_token"]

        # Device code flow
        flow = app.initiate_device_flow(scopes=self.SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow error: {flow.get('error_description')}")

        print("\n" + "═" * 60)
        print("  🔐  LOCALCLAW — ONE-TIME HOTMAIL LOGIN")
        print("═" * 60)
        print(f"\n  1. Open: {flow['verification_uri']}")
        print(f"  2. Code: {flow['user_code']}")
        print(f"  3. Sign in as: {self.address}")
        print(f"\n  LocalClaw never sees your password or 2FA code.")
        print(f"  Waiting...\n")

        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(
                f"Login failed: {result.get('error_description', result.get('error'))}"
            )

        self._persist(cache)
        print("  ✅  Token cached in OS keychain.\n")
        log.info("Hotmail token acquired and cached.")
        return result["access_token"]

    def _persist(self, cache) -> None:
        if cache.has_state_changed:
            keychain_set(self._cache_key, cache.serialize())

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _graph(self, method: str, path: str, **kwargs):
        resp = requests.request(method, f"{GRAPH_BASE}{path}",
                                headers=self._headers(), **kwargs)
        if resp.status_code == 401:
            log.info("Token expired — re-acquiring...")
            self._token = self._load_or_acquire_token()
            resp = requests.request(method, f"{GRAPH_BASE}{path}",
                                    headers=self._headers(), **kwargs)
        return resp

    def status(self) -> str:
        return self._status

    def fetch_unread(self) -> list[dict]:
        try:
            resp = self._graph("GET", "/me/mailFolders/inbox/messages", params={
                "$filter": "isRead eq false",
                "$select": "id,subject,from,body,receivedDateTime",
                "$top":    20,
                "$orderby": "receivedDateTime desc",
            })
            resp.raise_for_status()
            self._status = "ok"
            results = []
            for m in resp.json().get("value", []):
                body = m.get("body", {}).get("content", "")
                if m.get("body", {}).get("contentType") == "html":
                    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
                results.append({
                    "id":       m["id"],
                    "from":     m.get("from", {}).get("emailAddress", {}).get("address", ""),
                    "name":     m.get("from", {}).get("emailAddress", {}).get("name", ""),
                    "subject":  m.get("subject", "(no subject)"),
                    "body":     body,
                    "received": m.get("receivedDateTime", ""),
                })
            return results
        except Exception as exc:
            self._status = "error"
            log.error("fetch_unread failed: %s", exc)
            return []

    def send_reply(self, to: str, subject: str, body: str) -> bool:
        subj = f"Re: {subject}" if not subject.startswith("Re:") else subject
        try:
            self._graph("POST", "/me/sendMail", json={
                "message": {
                    "subject": subj,
                    "body":    {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                },
                "saveToSentItems": True,
            }).raise_for_status()
            log.info("Reply sent to %s", to)
            return True
        except Exception as exc:
            log.error("send_reply failed: %s", exc)
            return False

    def mark_read(self, mail_id: str) -> None:
        try:
            self._graph("PATCH", f"/me/messages/{mail_id}",
                        json={"isRead": True}).raise_for_status()
        except Exception as exc:
            log.warning("mark_read failed (non-critical): %s", exc)

    def delete(self, mail_id: str) -> None:
        try:
            self._graph("DELETE", f"/me/messages/{mail_id}").raise_for_status()
        except Exception as exc:
            log.warning("delete failed: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA
# ══════════════════════════════════════════════════════════════════════════════

_ollama_status = "unknown"


def ask_ollama(prompt: str, system_prompt: str = "") -> str:
    global _ollama_status
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [],
        "stream": False,
    }
    if system_prompt:
        payload["messages"].append({"role": "system", "content": system_prompt})
    payload["messages"].append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json=payload, timeout=120,
        )
        resp.raise_for_status()
        _ollama_status = "running"
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        _ollama_status = "offline"
        log.error("Cannot reach Ollama. Run: ollama serve")
        return "Sorry, I could not reach the local AI model right now."
    except Exception as exc:
        _ollama_status = "error"
        log.error("Ollama error: %s", exc)
        return f"Error: {exc}"


def check_ollama() -> str:
    try:
        r = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.ok:
            return "running"
    except Exception:
        pass
    return "offline"


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def process_email(email: dict, backend: HotmailBackend) -> dict:
    """Process one email: generate reply, optionally send, update memory."""
    sender  = email["from"]
    name    = email.get("name", sender)
    subject = email["subject"]
    body    = email["body"]

    log.info("New email | From: %s | Subject: %s", sender, subject)

    mem.record_sender(sender, name, subject)
    mem.increment_stat("emails_processed")

    if not body.strip():
        log.info("Skipping — empty body.")
        mem.increment_stat("emails_skipped")
        return {**email, "status": "skipped", "reply": ""}

    prompt = f"""You received an email:

FROM: {name} <{sender}>
SUBJECT: {subject}
---
{body[:3000]}
---

Write a helpful, professional reply."""

    system_prompt = mem.build_system_prompt()
    reply = ask_ollama(prompt, system_prompt)

    result = {**email, "status": "replied" if not config.DRY_RUN else "draft", "reply": reply}

    if config.DRY_RUN:
        log.info("[DRY RUN] Reply draft generated (%d chars).", len(reply))
    else:
        sent = backend.send_reply(sender, subject, reply)
        if sent:
            mem.increment_stat("replies_sent")
            result["status"] = "replied"
        else:
            result["status"] = "failed"

    backend.mark_read(email["id"])
    mem.record_email(result)

    if config.DELETE_AFTER_READ:
        backend.delete(email["id"])

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CRON JOBS
# ══════════════════════════════════════════════════════════════════════════════

_cron_jobs: dict[str, dict] = {
    "poll_inbox": {
        "name":     "Poll Inbox",
        "schedule": f"every {config.POLL_INTERVAL}s",
        "enabled":  True,
        "last_run": None,
        "next_run": None,
    },
    "daily_summary": {
        "name":     "Daily Summary",
        "schedule": "09:00 daily",
        "enabled":  True,
        "last_run": None,
        "next_run": None,
    },
    "memory_cleanup": {
        "name":     "Memory Cleanup",
        "schedule": "weekly Sunday",
        "enabled":  False,
        "last_run": None,
        "next_run": None,
    },
}


def run_daily_summary(backend: HotmailBackend) -> None:
    """Generate and log a daily summary using Ollama."""
    stats = mem.get_stats()
    emails = mem.get_emails()[:10]
    senders = mem.get_senders()

    top_senders = sorted(senders.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    sender_list = "\n".join(f"  - {e} ({v['count']} emails)" for e, v in top_senders)

    prompt = f"""Generate a brief daily summary for {config.OWNER_NAME}:

Stats today:
  - Emails processed: {stats.get('emails_processed', 0)}
  - Replies sent: {stats.get('replies_sent', 0)}

Top senders:
{sender_list}

Keep the summary to 3-4 sentences. Highlight anything notable."""

    summary = ask_ollama(prompt, mem.build_system_prompt())
    log.info("📋 Daily Summary:\n%s", summary)
    mem.add_log("info", f"Daily summary generated: {summary[:80]}...")
    _cron_jobs["daily_summary"]["last_run"] = datetime.datetime.now().isoformat()


def cron_scheduler(backend: HotmailBackend) -> None:
    """Runs cron jobs on a background thread."""
    last_daily = None
    while True:
        now = datetime.datetime.now()

        # Daily summary at 09:00
        if (
            _cron_jobs["daily_summary"]["enabled"]
            and now.hour == 9 and now.minute == 0
            and (last_daily is None or last_daily.date() < now.date())
        ):
            log.info("Running cron: daily summary")
            run_daily_summary(backend)
            last_daily = now

        time.sleep(60)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK REST API  — serves the dashboard
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)   # allow dashboard HTML to call the API

_backend: HotmailBackend | None = None


@app.route("/")
def index():
    return app.send_static_file("dashboard.html")


@app.route("/api/status")
def api_status():
    stats     = mem.get_stats()
    identity  = mem.get_identity()
    uptime_s  = mem.uptime_seconds()

    return jsonify({
        "gateway":   "online",
        "identity":  identity,
        "ollama":    check_ollama(),
        "hotmail":   _backend.status() if _backend else "not_started",
        "dry_run":   config.DRY_RUN,
        "model":     config.OLLAMA_MODEL,
        "poll_interval": config.POLL_INTERVAL,
        "uptime_seconds": uptime_s,
        "stats":     stats,
        "cron_jobs": _cron_jobs,
    })


@app.route("/api/emails")
def api_emails():
    limit = int(request.args.get("limit", 30))
    return jsonify(mem.get_emails()[:limit])


@app.route("/api/logs")
def api_logs():
    n = int(request.args.get("n", 50))
    return jsonify(mem.get_logs(n))


@app.route("/api/memory")
def api_memory():
    data = mem.get_all()
    return jsonify({
        "memory":   data.get("memory", {}),
        "senders":  data.get("senders", {}),
        "identity": data.get("identity", {}),
    })


@app.route("/api/memory", methods=["POST"])
def api_memory_set():
    body = request.get_json()
    key  = body.get("key", "").strip()
    val  = body.get("value", "").strip()
    if not key or not val:
        return jsonify({"error": "key and value required"}), 400
    mem.remember(key, val)
    log.info("Memory updated: %s = %s", key, val)
    return jsonify({"ok": True, "key": key, "value": val})


@app.route("/api/memory/<key>", methods=["DELETE"])
def api_memory_delete(key):
    mem.forget(key)
    log.info("Memory deleted: %s", key)
    return jsonify({"ok": True})


@app.route("/api/cron/<job_id>", methods=["PATCH"])
def api_cron_toggle(job_id):
    if job_id not in _cron_jobs:
        return jsonify({"error": "unknown job"}), 404
    body = request.get_json()
    _cron_jobs[job_id]["enabled"] = bool(body.get("enabled", True))
    state = "enabled" if _cron_jobs[job_id]["enabled"] else "disabled"
    log.info("Cron job '%s' %s", job_id, state)
    return jsonify({"ok": True, "job": _cron_jobs[job_id]})


@app.route("/api/reply", methods=["POST"])
def api_reply():
    """Manually trigger an AI reply to a given email ID."""
    body     = request.get_json()
    email_id = body.get("email_id")
    override = body.get("reply_text", "")

    if not email_id or not _backend:
        return jsonify({"error": "email_id required"}), 400

    if override:
        # Send a manually edited reply
        to      = body.get("to", "")
        subject = body.get("subject", "")
        sent    = _backend.send_reply(to, subject, override)
        if sent:
            mem.increment_stat("replies_sent")
        return jsonify({"ok": sent})

    return jsonify({"error": "No reply text provided"}), 400


@app.route("/api/generate_reply", methods=["POST"])
def api_generate_reply():
    """Ask Ollama to generate a reply for a given email body."""
    body = request.get_json()
    sender  = body.get("from", "")
    subject = body.get("subject", "")
    text    = body.get("body", "")

    if not text:
        return jsonify({"error": "body required"}), 400

    prompt = f"""FROM: {sender}
SUBJECT: {subject}
---
{text[:3000]}
---
Write a helpful, professional reply."""

    reply = ask_ollama(prompt, mem.build_system_prompt())
    return jsonify({"reply": reply})


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "owner":          config.OWNER_NAME,
        "assistant_name": config.ASSISTANT_NAME,
        "email":          config.EMAIL_ADDRESS,
        "model":          config.OLLAMA_MODEL,
        "poll_interval":  config.POLL_INTERVAL,
        "dry_run":        config.DRY_RUN,
        "dashboard_port": config.DASHBOARD_PORT,
    })


@app.route("/api/config", methods=["PATCH"])
def api_config_update():
    """Update runtime config (dry_run, poll_interval)."""
    body = request.get_json()
    if "dry_run" in body:
        config.DRY_RUN = bool(body["dry_run"])
        log.info("DRY_RUN set to %s via dashboard", config.DRY_RUN)
    if "poll_interval" in body:
        config.POLL_INTERVAL = int(body["poll_interval"])
        log.info("POLL_INTERVAL set to %ds via dashboard", config.POLL_INTERVAL)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# POLL LOOP
# ══════════════════════════════════════════════════════════════════════════════

def poll_loop(backend: HotmailBackend) -> None:
    poll_n = 0
    while True:
        poll_n += 1
        _cron_jobs["poll_inbox"]["last_run"] = datetime.datetime.now().isoformat()
        try:
            if _cron_jobs["poll_inbox"]["enabled"]:
                emails = backend.fetch_unread()
                if emails:
                    log.info("Poll #%d — %d new email(s)", poll_n, len(emails))
                    for email in emails:
                        process_email(email, backend)
                else:
                    log.info("Poll #%d — no new emails", poll_n)
        except Exception as exc:
            log.exception("Poll #%d error: %s", poll_n, exc)

        time.sleep(config.POLL_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run():
    global _backend

    log.info("=" * 60)
    log.info("🦞  LocalClaw Personal AI Gateway")
    log.info("Owner  : %s", config.OWNER_NAME)
    log.info("Model  : %s", config.OLLAMA_MODEL)
    log.info("Email  : %s", config.EMAIL_ADDRESS)
    log.info("Poll   : every %ds", config.POLL_INTERVAL)
    log.info("DryRun : %s", config.DRY_RUN)
    log.info("=" * 60)

    # Check Ollama
    ollama_ok = check_ollama()
    log.info("Ollama : %s", ollama_ok)

    # Initialise Hotmail backend
    _backend = HotmailBackend(address=config.EMAIL_ADDRESS)

    print(f"\n  ✅ LocalClaw is online")
    print(f"     Account : {config.EMAIL_ADDRESS}")
    print(f"     Model   : {config.OLLAMA_MODEL}")
    print(f"     Dashboard: http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    print()

    # Start poll loop in background thread
    t_poll = threading.Thread(target=poll_loop, args=(_backend,), daemon=True)
    t_poll.start()

    # Start cron scheduler in background thread
    t_cron = threading.Thread(target=cron_scheduler, args=(_backend,), daemon=True)
    t_cron.start()

    # Start Flask dashboard API (main thread)
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=config.DASHBOARD_DEBUG,
        use_reloader=False,
    )


if __name__ == "__main__":
    run()

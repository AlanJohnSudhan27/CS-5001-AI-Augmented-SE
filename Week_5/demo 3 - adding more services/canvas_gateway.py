"""
LocalClaw Canvas LMS Gateway
=============================
- Lists active courses and their activity (announcements, discussions, assignments)
- Exposes a Flask REST API on port 5002
- Shares memory.json and config.py with the email and GitHub gateways

Token: paste in config.py or leave blank to be prompted once (cached in keychain).
Get your token: Canvas → Account → Settings → "New Access Token"
"""

import time
import threading
import logging
import datetime
import re
from logging.handlers import RotatingFileHandler

import requests
import keyring
from flask import Flask, jsonify, request
from flask_cors import CORS

import config
import memory as mem


# ── Logging ───────────────────────────────────────────────────────────────────

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        level = record.levelname.lower()
        if level == "warning":
            level = "warn"
        mem.add_log(level, self.format(record))


log = logging.getLogger("localclaw.canvas")
log.setLevel(logging.INFO)

fmt = logging.Formatter("%(message)s")

fh = RotatingFileHandler("canvas_gateway.log", maxBytes=1_000_000, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(fh)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(sh)

mh = MemoryLogHandler()
mh.setFormatter(fmt)
log.addHandler(mh)


# ══════════════════════════════════════════════════════════════════════════════
# CANVAS BACKEND
# ══════════════════════════════════════════════════════════════════════════════

KEYRING_APP = "localclaw"
CANVAS_API  = "/api/v1"


class CanvasBackend:
    def __init__(self):
        self._base_url = config.CANVAS_BASE_URL.rstrip("/")
        self._token    = self._load_or_prompt_token()
        self._status   = "ok"

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _load_or_prompt_token(self) -> str:
        key   = "canvas_token"

        # 1. config.py takes priority
        if config.CANVAS_TOKEN:
            log.info("Canvas token loaded from config.py.")
            keyring.set_password(KEYRING_APP, key, config.CANVAS_TOKEN)
            return config.CANVAS_TOKEN

        # 2. fall back to keychain
        token = keyring.get_password(KEYRING_APP, key)
        if token:
            log.info("Canvas token loaded from keychain.")
            return token

        print("\n" + "═" * 60)
        print("  📚  LOCALCLAW — CANVAS TOKEN SETUP")
        print("═" * 60)
        print("\n  1. Go to: Canvas → Account → Settings")
        print("  2. Scroll to 'Approved Integrations'")
        print("  3. Click '+ New Access Token', set a purpose, generate it")
        print("  4. Paste the token below.")
        print()
        token = input("  Paste your Canvas API Access Token: ").strip()
        if not token:
            raise RuntimeError("No Canvas token provided.")
        keyring.set_password(KEYRING_APP, key, token)
        print("  ✅  Token cached in OS keychain.\n")
        log.info("Canvas token saved to keychain.")
        return token

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _req(self, method: str, path: str, **kwargs):
        url = self._base_url + CANVAS_API + path
        return requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)

    # ── Public interface ──────────────────────────────────────────────────────

    def status(self) -> str:
        return self._status

    def get_courses(self) -> list[dict]:
        try:
            resp = self._req(
                "GET", "/courses",
                params={"enrollment_state": "active", "per_page": 30,
                        "include[]": "term"},
            )
            if not resp.ok:
                return []
            courses = []
            for c in resp.json():
                if not isinstance(c, dict):
                    continue
                enrollments = c.get("enrollments", [])
                enrollment_type = enrollments[0].get("type", "") if enrollments else ""
                courses.append({
                    "id":              c["id"],
                    "name":            c.get("name", ""),
                    "course_code":     c.get("course_code", ""),
                    "enrollment_type": enrollment_type,
                    "start_at":        c.get("start_at", "") or "",
                    "end_at":          c.get("end_at", "") or "",
                })
            return courses
        except Exception as exc:
            log.error("get_courses failed: %s", exc)
            return []

    def get_course_activity(self, course_id: int) -> dict:
        announcements, discussions, assignments = [], [], []
        try:
            r = self._req("GET", "/announcements",
                          params={f"context_codes[]": f"course_{course_id}", "per_page": 5})
            if r.ok:
                for a in r.json():
                    announcements.append({
                        "title":     a.get("title", ""),
                        "message":   _strip_html(a.get("message", ""))[:200],
                        "posted_at": a.get("posted_at", ""),
                        "author":    a.get("author", {}).get("display_name", ""),
                    })
        except Exception as exc:
            log.debug("announcements fetch failed: %s", exc)

        try:
            r = self._req("GET", f"/courses/{course_id}/discussion_topics",
                          params={"per_page": 5})
            if r.ok:
                for d in r.json():
                    discussions.append({
                        "title":         d.get("title", ""),
                        "message":       _strip_html(d.get("message") or "")[:200],
                        "posted_at":     d.get("posted_at", ""),
                        "replies_count": d.get("discussion_subentry_count", 0),
                    })
        except Exception as exc:
            log.debug("discussions fetch failed: %s", exc)

        try:
            r = self._req("GET", f"/courses/{course_id}/assignments",
                          params={"bucket": "upcoming", "per_page": 5})
            if r.ok:
                for a in r.json():
                    assignments.append({
                        "name":             a.get("name", ""),
                        "due_at":           a.get("due_at", "") or "",
                        "points_possible":  a.get("points_possible"),
                        "submission_types": a.get("submission_types", []),
                    })
        except Exception as exc:
            log.debug("assignments fetch failed: %s", exc)

        return {
            "course_id":     course_id,
            "announcements": announcements,
            "discussions":   discussions,
            "assignments":   assignments,
        }


# ── HTML strip helper ─────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", text or "").strip()


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA  (self-contained copy)
# ══════════════════════════════════════════════════════════════════════════════

_ollama_status = "unknown"


def ask_ollama(prompt: str, system_prompt: str = "") -> str:
    global _ollama_status
    payload = {
        "model":    config.OLLAMA_MODEL,
        "messages": [],
        "stream":   False,
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
# CRON JOBS
# ══════════════════════════════════════════════════════════════════════════════

_cron_jobs: dict[str, dict] = {
    "poll_courses": {
        "name":     "Poll Courses",
        "schedule": f"every {config.CANVAS_POLL_INTERVAL}s",
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
}


def run_daily_summary() -> None:
    stats = mem.get_stats()
    prompt = f"""Generate a brief daily Canvas LMS activity summary for {config.OWNER_NAME}:

  - Messages processed: {stats.get('emails_processed', 0)}
  - Replies sent: {stats.get('replies_sent', 0)}

Keep it to 2-3 sentences."""
    summary = ask_ollama(prompt, mem.build_system_prompt())
    log.info("📋 Daily Canvas Summary:\n%s", summary)
    _cron_jobs["daily_summary"]["last_run"] = datetime.datetime.now().isoformat()


def cron_scheduler() -> None:
    last_daily = None
    while True:
        now = datetime.datetime.now()
        if (
            _cron_jobs["daily_summary"]["enabled"]
            and now.hour == 9 and now.minute == 0
            and (last_daily is None or last_daily.date() < now.date())
        ):
            log.info("Running cron: daily summary")
            run_daily_summary()
            last_daily = now
        time.sleep(60)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK REST API
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

_backend: CanvasBackend | None = None


@app.route("/")
def index():
    return jsonify({
        "service":   "LocalClaw Canvas Gateway",
        "status":    "online",
        "note":      "This is a REST API — open the dashboard at http://127.0.0.1:5000",
        "endpoints": ["/api/status", "/api/courses", "/api/course/<id>/activity",
                      "/api/logs", "/api/memory", "/api/config"],
    })


@app.route("/api/status")
def api_status():
    return jsonify({
        "gateway":        "online",
        "channel":        "canvas",
        "canvas":         _backend.status() if _backend else "not_started",
        "ollama":         check_ollama(),
        "dry_run":        config.DRY_RUN,
        "auto_reply":     config.CANVAS_AUTO_REPLY,
        "model":          config.OLLAMA_MODEL,
        "poll_interval":  config.CANVAS_POLL_INTERVAL,
        "base_url":       config.CANVAS_BASE_URL,
        "uptime_seconds": mem.uptime_seconds(),
        "stats":          mem.get_stats(),
        "cron_jobs":      _cron_jobs,
    })


@app.route("/api/courses")
def api_courses():
    if not _backend:
        return jsonify({"error": "not started"}), 503
    return jsonify(_backend.get_courses())


@app.route("/api/course/<int:course_id>/activity")
def api_course_activity(course_id):
    if not _backend:
        return jsonify({"error": "not started"}), 503
    return jsonify(_backend.get_course_activity(course_id))


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
    return jsonify({"ok": True, "key": key, "value": val})


@app.route("/api/memory/<key>", methods=["DELETE"])
def api_memory_delete(key):
    mem.forget(key)
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


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "owner":          config.OWNER_NAME,
        "base_url":       config.CANVAS_BASE_URL,
        "model":          config.OLLAMA_MODEL,
        "poll_interval":  config.CANVAS_POLL_INTERVAL,
        "dry_run":        config.DRY_RUN,
        "auto_reply":     config.CANVAS_AUTO_REPLY,
        "gateway_port":   config.CANVAS_GATEWAY_PORT,
    })


@app.route("/api/config", methods=["PATCH"])
def api_config_update():
    body = request.get_json()
    if "dry_run" in body:
        config.DRY_RUN = bool(body["dry_run"])
        log.info("DRY_RUN set to %s", config.DRY_RUN)
    if "auto_reply" in body:
        config.CANVAS_AUTO_REPLY = bool(body["auto_reply"])
        log.info("CANVAS_AUTO_REPLY set to %s", config.CANVAS_AUTO_REPLY)
    if "poll_interval" in body:
        config.CANVAS_POLL_INTERVAL = int(body["poll_interval"])
        log.info("CANVAS_POLL_INTERVAL set to %ds", config.CANVAS_POLL_INTERVAL)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# POLL LOOP
# ══════════════════════════════════════════════════════════════════════════════

def poll_loop(backend: CanvasBackend) -> None:
    poll_n = 0
    while True:
        poll_n += 1
        _cron_jobs["poll_courses"]["last_run"] = datetime.datetime.now().isoformat()
        try:
            if _cron_jobs["poll_courses"]["enabled"]:
                courses = backend.get_courses()
                log.info("Poll #%d — %d active course(s)", poll_n, len(courses))
        except Exception as exc:
            log.exception("Poll #%d error: %s", poll_n, exc)
        time.sleep(config.CANVAS_POLL_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run():
    global _backend

    log.info("=" * 60)
    log.info("📚  LocalClaw Canvas Gateway")
    log.info("Owner     : %s", config.OWNER_NAME)
    log.info("Base URL  : %s", config.CANVAS_BASE_URL)
    log.info("Model     : %s", config.OLLAMA_MODEL)
    log.info("Poll      : every %ds", config.CANVAS_POLL_INTERVAL)
    log.info("DryRun    : %s", config.DRY_RUN)
    log.info("AutoReply : %s", config.CANVAS_AUTO_REPLY)
    log.info("=" * 60)

    _backend = CanvasBackend()

    print(f"\n  ✅  LocalClaw Canvas Gateway is online")
    print(f"     Base URL  : {config.CANVAS_BASE_URL}")
    print(f"     Model     : {config.OLLAMA_MODEL}")
    print(f"     API       : http://{config.CANVAS_GATEWAY_HOST}:{config.CANVAS_GATEWAY_PORT}")
    print()

    t_poll = threading.Thread(target=poll_loop, args=(_backend,), daemon=True)
    t_poll.start()

    t_cron = threading.Thread(target=cron_scheduler, daemon=True)
    t_cron.start()

    app.run(
        host=config.CANVAS_GATEWAY_HOST,
        port=config.CANVAS_GATEWAY_PORT,
        debug=config.CANVAS_GATEWAY_DEBUG,
        use_reloader=False,
    )


if __name__ == "__main__":
    run()

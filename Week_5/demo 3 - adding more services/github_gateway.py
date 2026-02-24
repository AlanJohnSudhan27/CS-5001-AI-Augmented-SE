"""
LocalClaw GitHub Gateway
========================
- Polls GitHub notifications via REST API (issues, PRs, mentions, CI, releases)
- Generates AI replies using local Ollama model
- Posts comments on issues/PRs when GITHUB_AUTO_REPLY is enabled
- Exposes a Flask REST API on port 5001
- Shares memory.json and config.py with the email gateway

Token: prompted once on first run, then cached in OS keychain.
Never stored in code or config files.
"""

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
    def emit(self, record):
        level = record.levelname.lower()
        if level == "warning":
            level = "warn"
        mem.add_log(level, self.format(record))


log = logging.getLogger("localclaw.github")
log.setLevel(logging.INFO)

fmt = logging.Formatter("%(message)s")

fh = RotatingFileHandler("github_gateway.log", maxBytes=1_000_000, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(fh)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(sh)

mh = MemoryLogHandler()
mh.setFormatter(fmt)
log.addHandler(mh)


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB BACKEND
# ══════════════════════════════════════════════════════════════════════════════

KEYRING_APP = "localclaw"
GITHUB_API  = "https://api.github.com"


class GitHubBackend:
    def __init__(self, username: str):
        self.username = username
        self._token   = self._load_or_prompt_token()
        self._status  = "ok"

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _load_or_prompt_token(self) -> str:
        key   = f"github_token_{self.username}"

        # 1. config.py takes priority
        if config.GITHUB_TOKEN:
            log.info("GitHub token loaded from config.py.")
            keyring.set_password(KEYRING_APP, key, config.GITHUB_TOKEN)
            return config.GITHUB_TOKEN

        # 2. fall back to keychain
        token = keyring.get_password(KEYRING_APP, key)
        if token:
            log.info("GitHub token loaded from keychain.")
            return token

        print("\n" + "═" * 60)
        print("  🐙  LOCALCLAW — GITHUB TOKEN SETUP")
        print("═" * 60)
        print("\n  1. Go to: https://github.com/settings/tokens/new")
        print("  2. Select scopes: notifications  +  repo")
        print("  3. Generate and paste it below.")
        print()
        token = input("  Paste your GitHub Personal Access Token: ").strip()
        if not token:
            raise RuntimeError("No GitHub token provided.")
        keyring.set_password(KEYRING_APP, key, token)
        print("  ✅  Token cached in OS keychain.\n")
        log.info("GitHub token saved to keychain.")
        return token

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization":        f"token {self._token}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _req(self, method: str, url: str, **kwargs):
        return requests.request(
            method, url, headers=self._headers(), timeout=30, **kwargs
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def status(self) -> str:
        return self._status

    def fetch_unread(self) -> list[dict]:
        try:
            resp = self._req(
                "GET",
                f"{GITHUB_API}/notifications",
                params={"all": "false", "per_page": 20},
            )
            resp.raise_for_status()
            self._status = "ok"

            results = []
            for n in resp.json():
                sub   = n.get("subject", {})
                stype = sub.get("type", "")          # Issue, PullRequest, Release, Commit
                surl  = sub.get("url", "")
                repo  = n.get("repository", {}).get("full_name", "")

                body, comments_url = self._fetch_subject(stype, surl)

                results.append({
                    "id":           n["id"],
                    "from":         repo,
                    "name":         repo,
                    "subject":      sub.get("title", "(no title)"),
                    "body":         body,
                    "received":     n.get("updated_at", ""),
                    "type":         stype,
                    "repo":         repo,
                    "comments_url": comments_url,
                    "channel":      "github",
                })
            return results

        except Exception as exc:
            self._status = "error"
            log.error("fetch_unread failed: %s", exc)
            return []

    def _fetch_subject(self, stype: str, surl: str) -> tuple[str, str]:
        """Fetch the body text and comments URL for a notification subject."""
        body         = ""
        comments_url = ""
        if not surl:
            return body, comments_url
        try:
            r = self._req("GET", surl)
            if not r.ok:
                return body, comments_url
            data = r.json()
            if stype in ("Issue", "PullRequest"):
                body         = data.get("body") or ""
                # Issues have comments_url; PRs: fall back to converting the URL
                comments_url = (
                    data.get("comments_url")
                    or surl.replace("/pulls/", "/issues/") + "/comments"
                )
            elif stype == "Release":
                body = data.get("body") or data.get("name") or ""
            elif stype == "Commit":
                body = data.get("commit", {}).get("message", "")
            else:
                body = data.get("body") or ""
        except Exception as exc:
            log.debug("Could not fetch subject details: %s", exc)
        return body, comments_url

    def post_comment(self, comments_url: str, body: str) -> bool:
        if not comments_url:
            log.warning("No comments_url — cannot post reply.")
            return False
        try:
            self._req("POST", comments_url, json={"body": body}).raise_for_status()
            log.info("Comment posted to %s", comments_url)
            return True
        except Exception as exc:
            log.error("post_comment failed: %s", exc)
            return False

    def mark_read(self, thread_id: str) -> None:
        try:
            self._req(
                "PATCH", f"{GITHUB_API}/notifications/threads/{thread_id}"
            ).raise_for_status()
        except Exception as exc:
            log.warning("mark_read failed (non-critical): %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA  (same as email gateway — self-contained copy)
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
# NOTIFICATION PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def process_notification(notif: dict, backend: GitHubBackend) -> dict:
    """Process one GitHub notification: generate reply, optionally post, update memory."""
    repo    = notif["repo"]
    subject = notif["subject"]
    body    = notif["body"]
    ntype   = notif["type"]

    log.info("New GitHub notification | %s | %s: %s", repo, ntype, subject)

    mem.record_sender(repo, repo, subject)
    mem.increment_stat("emails_processed")

    prompt = f"""You received a GitHub {ntype} notification:

REPOSITORY: {repo}
{ntype.upper()}: {subject}
---
{body[:3000] if body else "(no description provided)"}
---

Write a concise, helpful technical comment or acknowledgement."""

    reply  = ask_ollama(prompt, mem.build_system_prompt())
    status = "draft"

    if config.DRY_RUN:
        log.info("[DRY RUN] GitHub reply drafted (%d chars).", len(reply))
    elif config.GITHUB_AUTO_REPLY and notif.get("comments_url"):
        sent = backend.post_comment(notif["comments_url"], reply)
        if sent:
            mem.increment_stat("replies_sent")
            status = "replied"
        else:
            status = "failed"
    else:
        log.info("Reply drafted — AUTO_REPLY is disabled, not posting.")

    backend.mark_read(notif["id"])

    result = {**notif, "reply": reply, "status": status}
    mem.record_email(result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CRON JOBS
# ══════════════════════════════════════════════════════════════════════════════

_cron_jobs: dict[str, dict] = {
    "poll_notifications": {
        "name":     "Poll Notifications",
        "schedule": f"every {config.GITHUB_POLL_INTERVAL}s",
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
    prompt = f"""Generate a brief daily GitHub activity summary for {config.OWNER_NAME}:

  - Notifications processed: {stats.get('emails_processed', 0)}
  - Comments posted: {stats.get('replies_sent', 0)}

Keep it to 2-3 sentences. Highlight anything notable."""
    summary = ask_ollama(prompt, mem.build_system_prompt())
    log.info("📋 Daily GitHub Summary:\n%s", summary)
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

_backend: GitHubBackend | None = None


@app.route("/")
def index():
    return jsonify({
        "service":   "LocalClaw GitHub Gateway",
        "status":    "online",
        "note":      "This is a REST API — open the dashboard at http://127.0.0.1:5000",
        "endpoints": ["/api/status", "/api/repos", "/api/repo/<owner>/<repo>/activity",
                      "/api/notifications", "/api/logs",
                      "/api/memory", "/api/generate_reply", "/api/reply", "/api/config"],
    })


@app.route("/api/status")
def api_status():
    return jsonify({
        "gateway":        "online",
        "channel":        "github",
        "github":         _backend.status() if _backend else "not_started",
        "ollama":         check_ollama(),
        "dry_run":        config.DRY_RUN,
        "auto_reply":     config.GITHUB_AUTO_REPLY,
        "model":          config.OLLAMA_MODEL,
        "poll_interval":  config.GITHUB_POLL_INTERVAL,
        "uptime_seconds": mem.uptime_seconds(),
        "stats":          mem.get_stats(),
        "cron_jobs":      _cron_jobs,
    })


@app.route("/api/notifications")
def api_notifications():
    limit       = int(request.args.get("limit", 30))
    all_items   = mem.get_emails()
    github_only = [e for e in all_items if e.get("channel") == "github"]
    return jsonify(github_only[:limit])


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


@app.route("/api/generate_reply", methods=["POST"])
def api_generate_reply():
    body    = request.get_json()
    repo    = body.get("from", "")
    subject = body.get("subject", "")
    text    = body.get("body", "")
    ntype   = body.get("type", "Issue")
    if not text:
        return jsonify({"error": "body required"}), 400
    prompt = f"""REPOSITORY: {repo}
{ntype.upper()}: {subject}
---
{text[:3000]}
---
Write a concise, helpful technical comment."""
    reply = ask_ollama(prompt, mem.build_system_prompt())
    return jsonify({"reply": reply})


@app.route("/api/reply", methods=["POST"])
def api_reply():
    """Post a (possibly edited) comment to a GitHub issue/PR."""
    body         = request.get_json()
    comments_url = body.get("comments_url", "")
    reply_text   = body.get("reply_text", "")
    if not comments_url or not reply_text or not _backend:
        return jsonify({"error": "comments_url and reply_text required"}), 400
    sent = _backend.post_comment(comments_url, reply_text)
    if sent:
        mem.increment_stat("replies_sent")
    return jsonify({"ok": sent})


@app.route("/api/repos")
def api_repos():
    if not _backend:
        return jsonify({"error": "not started"}), 503
    try:
        r = _backend._req(
            "GET", f"{GITHUB_API}/user/repos",
            params={"sort": "pushed", "per_page": 30, "type": "owner"},
        )
        r.raise_for_status()
        repos = []
        for repo in r.json():
            repos.append({
                "name":        repo["name"],
                "full_name":   repo["full_name"],
                "description": repo.get("description") or "",
                "language":    repo.get("language") or "",
                "stars":       repo.get("stargazers_count", 0),
                "forks":       repo.get("forks_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
                "pushed_at":   repo.get("pushed_at", ""),
                "private":     repo.get("private", False),
            })
        return jsonify(repos)
    except Exception as exc:
        log.error("api_repos failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/repo/<owner>/<path:repo_name>/activity")
def api_repo_activity(owner, repo_name):
    if not _backend:
        return jsonify({"error": "not started"}), 503
    full = f"{owner}/{repo_name}"
    try:
        issues_r   = _backend._req("GET", f"{GITHUB_API}/repos/{full}/issues",
                                   params={"state": "open", "per_page": 10, "sort": "updated"})
        prs_r      = _backend._req("GET", f"{GITHUB_API}/repos/{full}/pulls",
                                   params={"state": "open", "per_page": 10, "sort": "updated"})
        releases_r = _backend._req("GET", f"{GITHUB_API}/repos/{full}/releases",
                                   params={"per_page": 5})

        def fmt_issue(i):
            return {
                "number":     i["number"],
                "title":      i["title"],
                "state":      i["state"],
                "user":       i["user"]["login"],
                "created_at": i["created_at"],
                "updated_at": i["updated_at"],
                "comments":   i.get("comments", 0),
                "labels":     [lbl["name"] for lbl in i.get("labels", [])],
            }

        def fmt_release(rel):
            return {
                "tag_name":    rel["tag_name"],
                "name":        rel.get("name") or rel["tag_name"],
                "published_at": rel.get("published_at", ""),
                "prerelease":  rel.get("prerelease", False),
            }

        issues = [fmt_issue(i) for i in (issues_r.json() if issues_r.ok else [])
                  if not i.get("pull_request")]
        prs    = [fmt_issue(i) for i in (prs_r.json()    if prs_r.ok    else [])]
        rels   = [fmt_release(i) for i in (releases_r.json() if releases_r.ok else [])]

        return jsonify({"repo": full, "issues": issues, "pull_requests": prs, "releases": rels})
    except Exception as exc:
        log.error("api_repo_activity failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "owner":          config.OWNER_NAME,
        "username":       config.GITHUB_USERNAME,
        "model":          config.OLLAMA_MODEL,
        "poll_interval":  config.GITHUB_POLL_INTERVAL,
        "dry_run":        config.DRY_RUN,
        "auto_reply":     config.GITHUB_AUTO_REPLY,
        "gateway_port":   config.GITHUB_GATEWAY_PORT,
    })


@app.route("/api/config", methods=["PATCH"])
def api_config_update():
    body = request.get_json()
    if "dry_run" in body:
        config.DRY_RUN = bool(body["dry_run"])
        log.info("DRY_RUN set to %s", config.DRY_RUN)
    if "auto_reply" in body:
        config.GITHUB_AUTO_REPLY = bool(body["auto_reply"])
        log.info("GITHUB_AUTO_REPLY set to %s", config.GITHUB_AUTO_REPLY)
    if "poll_interval" in body:
        config.GITHUB_POLL_INTERVAL = int(body["poll_interval"])
        log.info("GITHUB_POLL_INTERVAL set to %ds", config.GITHUB_POLL_INTERVAL)
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# POLL LOOP
# ══════════════════════════════════════════════════════════════════════════════

def poll_loop(backend: GitHubBackend) -> None:
    poll_n = 0
    while True:
        poll_n += 1
        _cron_jobs["poll_notifications"]["last_run"] = datetime.datetime.now().isoformat()
        try:
            if _cron_jobs["poll_notifications"]["enabled"]:
                notifs = backend.fetch_unread()
                if notifs:
                    log.info("Poll #%d — %d new notification(s)", poll_n, len(notifs))
                    for notif in notifs:
                        process_notification(notif, backend)
                else:
                    log.info("Poll #%d — no new notifications", poll_n)
        except Exception as exc:
            log.exception("Poll #%d error: %s", poll_n, exc)
        time.sleep(config.GITHUB_POLL_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run():
    global _backend

    log.info("=" * 60)
    log.info("🐙  LocalClaw GitHub Gateway")
    log.info("Owner     : %s", config.OWNER_NAME)
    log.info("Username  : %s", config.GITHUB_USERNAME)
    log.info("Model     : %s", config.OLLAMA_MODEL)
    log.info("Poll      : every %ds", config.GITHUB_POLL_INTERVAL)
    log.info("DryRun    : %s", config.DRY_RUN)
    log.info("AutoReply : %s", config.GITHUB_AUTO_REPLY)
    log.info("=" * 60)

    _backend = GitHubBackend(username=config.GITHUB_USERNAME)

    print(f"\n  ✅  LocalClaw GitHub Gateway is online")
    print(f"     Username  : {config.GITHUB_USERNAME}")
    print(f"     Model     : {config.OLLAMA_MODEL}")
    print(f"     Dashboard : http://{config.GITHUB_GATEWAY_HOST}:{config.GITHUB_GATEWAY_PORT}")
    print()

    t_poll = threading.Thread(target=poll_loop, args=(_backend,), daemon=True)
    t_poll.start()

    t_cron = threading.Thread(target=cron_scheduler, daemon=True)
    t_cron.start()

    app.run(
        host=config.GITHUB_GATEWAY_HOST,
        port=config.GITHUB_GATEWAY_PORT,
        debug=config.GITHUB_GATEWAY_DEBUG,
        use_reloader=False,
    )


if __name__ == "__main__":
    run()

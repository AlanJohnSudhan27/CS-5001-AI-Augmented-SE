# 🦞 LocalClaw — Personal AI Gateway

Your own personal AI email assistant. Local. Private. Yours.

---

## What it does

- **Polls your Hotmail inbox** via Microsoft Graph API
- **Generates replies** using a local Ollama model (no cloud AI)
- **Remembers context** across sessions (memory.json)
- **Runs cron jobs** (daily summary, memory cleanup)
- **Serves a control dashboard** at `http://localhost:5000`

---

## Project Structure

```
localclaw/
├── gateway.py       ← Main daemon (email + Ollama + Flask API + cron)
├── memory.py        ← Persistent memory & personality module
├── config.py        ← All settings (no passwords)
├── dashboard.html   ← Control dashboard (open in browser)
├── reset_token.py   ← Clear cached OAuth token
├── requirements.txt ← Python dependencies
├── memory.json      ← Auto-created: persistent memory store
└── gateway.log      ← Auto-created: rotating log file
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Ollama + pull a model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
ollama serve        # keep this running
```

### 3. Configure

Edit `config.py`:

```python
OWNER_NAME    = "Your Name"
EMAIL_ADDRESS = "you@hotmail.com"
OLLAMA_MODEL  = "llama3.2:3b"
DRY_RUN       = True     # set False when ready to send real replies
```

### 4. Run

```bash
python gateway.py
```

**First run:** A browser-based Microsoft login will appear (device flow).  
Open the URL, enter the code, sign in — LocalClaw never sees your password.  
Token is cached in your OS keychain for ~90 days.

### 5. Open the dashboard

```
http://localhost:5000
```

Or open `dashboard.html` directly in your browser (it calls the same API).

---

## Dashboard Features

| Panel | What it shows |
|---|---|
| Stats row | Emails processed, replies sent, pending, uptime |
| Email feed | All processed emails with status dots |
| Email modal | Full email + AI reply draft (editable) + send button |
| Memory | Add/delete persistent facts LocalClaw remembers |
| Cron Jobs | Toggle scheduled tasks on/off |
| Logs | Live log stream from the gateway |
| Settings | Toggle dry run, change poll interval |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/status` | Gateway status, stats, system health |
| GET | `/api/emails` | Processed email history |
| GET | `/api/logs` | Log buffer |
| GET/POST | `/api/memory` | Read/write persistent memory |
| DELETE | `/api/memory/<key>` | Delete a memory |
| PATCH | `/api/cron/<job_id>` | Enable/disable a cron job |
| POST | `/api/generate_reply` | Ask Ollama to generate a reply |
| POST | `/api/reply` | Send a reply via Graph API |
| GET/PATCH | `/api/config` | Read/update runtime config |

---

## Reset OAuth token

If you need to re-authenticate (e.g. after changing scopes):

```bash
python reset_token.py
```

---

## Roadmap

- [ ] Persistent memory & personality ← next
- [ ] Proactive cron jobs (daily digest, reminders)
- [ ] Multi-channel support (Telegram, Discord)
- [ ] Skills/plugin system

# LocalClaw 🦞
### Personal AI Email Assistant — Guerrilla Mail + Ollama Edition

Zero sign-up. Zero credentials. No cloud. Built from scratch in Python.

---

## Project Structure

```
localclaw/
├── main.py                  ← Entry point + CLI
├── requirements.txt         ← Dependencies
└── core/
    ├── config.py            ← All settings
    ├── logger.py            ← File + stream logging
    ├── guerrillamail.py     ← Guerrilla Mail API client
    ├── ollama.py            ← Ollama local LLM client
    ├── processor.py         ← Email → prompt → reply pipeline
    └── gateway.py           ← Poll loop + orchestration
```

---

## Quickstart

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Ollama + pull a model
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
ollama serve
```

### 3. Run
```bash
python main.py
```

Your disposable inbox address is printed on startup. Send any email there and LocalClaw will read it and generate an AI reply.

---

## CLI Options

```
python main.py --help

  --inbox    -i   Custom inbox name (e.g. myclaw → myclaw@guerrillamailblock.com)
  --model    -m   Ollama model to use (e.g. mistral, phi3)
  --dry-run  -d   Log AI replies without taking any action
  --poll     -p   Poll interval in seconds
  --list-models   List available Ollama models and exit
```

Examples:
```bash
python main.py --inbox myclaw --model mistral --poll 20
python main.py --dry-run
python main.py --list-models
```

---

## Configuration

Edit `core/config.py` to set defaults:

| Setting                | Default     | Description                               |
|------------------------|-------------|-------------------------------------------|
| `GUERRILLA_EMAIL_USER` | `""`        | Fixed inbox name, or `""` for random      |
| `OLLAMA_BASE_URL`      | `localhost` | Ollama server URL                         |
| `OLLAMA_MODEL`         | `"llama3"`  | Model to use for replies                  |
| `POLL_INTERVAL`        | `30`        | Seconds between inbox checks              |
| `DRY_RUN`              | `True`      | Log replies only, don't act               |
| `DELETE_AFTER_READ`    | `False`     | Delete emails after processing            |
| `MAX_BODY_CHARS`       | `3000`      | Truncate long email bodies before sending |
| `SYSTEM_PROMPT`        | (see file)  | AI persona / instructions                 |

---

## Sending Replies

Guerrilla Mail is **receive-only** — it has no outbound SMTP. Replies are logged to the terminal and `localclaw.log`.

To actually send replies, implement the `_send_reply()` hook in `core/processor.py`. A commented Gmail SMTP example is already included there.

---

## Notes

- Guerrilla Mail inboxes expire after **60 minutes** of inactivity.
- Don't set `POLL_INTERVAL` below **15 seconds** to avoid rate limiting.
- Start with `DRY_RUN = True` to review AI output before going live.

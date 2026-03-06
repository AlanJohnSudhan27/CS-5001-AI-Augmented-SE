# Code Review Orchestra

> **LLM Agent Orchestration Demo** — CS 5001: AI-Augmented Software Engineering
> Missouri S&T

A production-style demo of **multi-agent LLM orchestration** using Ollama + llama3.2:3b.
Four specialized AI agents collaborate in a pipeline to review source code — each one
building on the previous agent's structured output.

---

## What This Demonstrates

| Concept | Where it appears |
|---|---|
| **Context-gather pattern** | Each agent calls Python tools first, then sends all context to the LLM in one prompt |
| **`format="json"` enforcement** | Ollama `format="json"` guarantees structured output from a small local model |
| **Sequential pipeline** | `orchestrator.py` — each agent receives the prior agent's structured output |
| **Parallel orchestration** | `--parallel` flag — Reviewer + Suggester run concurrently via `asyncio.gather` |
| **Structured outputs** | `models/schemas.py` — typed `@dataclass` results passed between agents |
| **SSE streaming** | `web/` — live pipeline events streamed to browser via Server-Sent Events |
| **No frameworks** | Pure Python + Ollama REST API — no LangChain, no CrewAI |

---

## Pipeline

```
┌──────────────────────────────────────────────────────────┐
│                      Orchestrator                        │
│                                                          │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐        │
│  │  Analyzer  │ → │  Reviewer  │ → │  Suggester │ →  ┐   │
│  └────────────┘   └────────────┘   └────────────┘    │   │
│  Python reads     Python reads     Python reads      │   │
│  files → sends    files → sends    files → sends     │   │
│  to LLM           to LLM           to LLM            │   │
│                                                      ↓   │
│                                            ┌─────────────┤
│                                            │  Summarizer │
│                                            └─────────────┤
│                                            Scores 0-100  │
│                                            Executive     │
│                                            summary       │
└──────────────────────────────────────────────────────────┘
```

**Parallel mode** (`--parallel`): Reviewer and Suggester run concurrently —
`asyncio.gather` halves wall-clock time for stages 2 and 3.

---

## How the Context-Gather Pattern Works

With a small local model like llama3.2:3b, autonomous tool-calling is unreliable.
Instead, **Python does the tool work**; the LLM only does reasoning:

```
┌──────────────────────────────────────────────────────────┐
│  Ollama tool-use                                         │
│                                                          │
│  LLM ──requests tool──► Python ──result──► LLM (loop)    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  Context-gather pattern (this project)                   │
│                                                          │
│  Python reads files ──► builds prompt ──► LLM (once)     │
│                            format="json"                 │
└──────────────────────────────────────────────────────────┘
```

Each agent:
```python
# 1. Python gathers context
content = read_file("/path/to/file.py")   # Python function call

# 2. Build a comprehensive prompt
prompt = f"Analyze this code:\n{content}\nReturn JSON."

# 3. One LLM call with format="json"
raw = self.chat([{"role": "user", "content": prompt}])

# 4. Parse structured output
return AnalysisResult.from_dict(self._parse_json(raw))
```

---

## Tools (called by Python, not by the LLM)

| Function | Description |
|---|---|
| `read_file(path)` | Read source code (capped at 6 k chars) |
| `list_directory(path)` | Discover files and subdirectories |
| `get_file_stats(path)` | Size, line count, modification time |

---

## Project Structure

```
code-review-orchestra/
├── agents/
│   ├── base.py           # Ollama httpx call + JSON extraction (3 strategies)
│   ├── analyzer.py       # Stage 1 → AnalysisResult
│   ├── reviewer.py       # Stage 2 → ReviewResult
│   ├── suggester.py      # Stage 3 → SuggestionResult
│   └── summarizer.py     # Stage 4 → FinalReport
├── tools/
│   └── code_tools.py     # read_file, list_directory, get_file_stats
├── models/
│   └── schemas.py        # Typed dataclasses for all pipeline outputs
├── web/
│   ├── main.py           # FastAPI app
│   ├── routes.py         # POST /api/review, GET /api/stream/{id}
│   ├── jobs.py           # asyncio.Queue job registry
│   └── static/
│       └── index.html    # Vanilla JS SPA with live pipeline visualization
├── orchestrator.py       # Sequential + parallel pipeline runner
├── cli.py                # Click CLI with Rich output
├── config.py             # Settings via .env
├── .env.example          # Config template
└── requirements.txt
```

---

## Setup

**1. Pull the model**

```bash
ollama pull llama3.2:3b
ollama serve          # keep running in a terminal
```

**2. Install dependencies**

```bash
cd code-review-orchestra
pip install -r requirements.txt
```

**3. Configure (optional)**

```
configure `.env` as you like
# Defaults work out of the box if Ollama runs on localhost:11434
```
---

## Usage

### CLI

```bash
# Sequential pipeline (default)
python cli.py review /path/to/file.py

# Review a whole directory
python cli.py review /path/to/project/

# Parallel mode — Reviewer + Suggester run concurrently
python cli.py review /path/to/file.py --parallel

# Print last saved report
python cli.py last

# Raw JSON output
python cli.py review /path/to/file.py --output json
```

### Web UI

```bash
uvicorn web.main:app --reload --port 8001
```

Open [http://localhost:8001](http://localhost:8001):

1. **Enter a path** manually, or click **📁 Browse** to open the file browser
2. Navigate directories, single-click to select, double-click to enter a folder
3. Use "Select this folder" to review an entire directory
4. Tick **Parallel mode** if you want Reviewer + Suggester to run concurrently
5. Click **▶ Run Review** and watch the pipeline stream live

**Pipeline log features:**
- Each agent stage is separated by a labelled divider
- Tool calls (file reads) appear dim + italic with a `⟳` prefix — distinct from reasoning output
- Timestamps on every line (`HH:MM:SS`)
- Colour-coded agent badges (blue / purple / green / yellow)

---

## Agent Outputs

| Agent | Output | Key fields |
|---|---|---|
| Analyzer | `AnalysisResult` | `files_analyzed`, `functions`, `classes`, `complexity_notes`, `loc_total` |
| Reviewer | `ReviewResult` | `issues[]` (severity, category, location, evidence), `overall_risk` |
| Suggester | `SuggestionResult` | `improvements[]` (before/after snippets), `quick_wins` |
| Summarizer | `FinalReport` | `overall_score` (0-100), `executive_summary`, `critical_findings` |

---

## Stack

- **LLM:** `llama3.2:3b` via [Ollama](https://ollama.com/) REST API (`httpx`)
- **CLI:** [Click](https://click.palletsprojects.com/) + [Rich](https://github.com/Textualize/rich)
- **API:** [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Streaming:** Server-Sent Events (SSE) + vanilla JS `EventSource`
- **Config:** [python-dotenv](https://github.com/theskumar/python-dotenv)

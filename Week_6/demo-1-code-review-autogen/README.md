# Code Review — AutoGen

> **LLM Agent Orchestration Demo (AutoGen variant)** — CS 5001: AI-Augmented Software Engineering
> Missouri S&T

The same 4-agent code review pipeline as `code-review-orchestra/`, rebuilt with
**Microsoft AutoGen** (`autogen-agentchat` v0.4).

---

## Why AutoGen?

| | `code-review-orchestra` (pure Python) | `code-review-autogen` (AutoGen) |
|---|---|---|
| **LLM ↔ tools** | Python calls tools, feeds all context in one prompt | LLM decides when to call tools; AutoGen executes and loops |
| **Agentic loop** | Manual (explicit Python) | Built-in (`AssistantAgent`) |
| **Dependencies** | `httpx` only | `autogen-agentchat` + `autogen-ext` |
| **Transparency** | Every step is visible in your code | AutoGen manages the loop internally |
| **Reliability with small models** | High — no tool-calling required | Varies — llama3.2:3b has limited tool-calling |

**Key insight:** AutoGen implements the real *agentic loop* — the LLM requests a tool,
AutoGen runs it, the result goes back to the LLM, and the cycle repeats until the LLM
stops calling tools. The original project skips this loop entirely by having Python
gather all context first.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  AutoGen agentic loop (per agent)                            │
│                                                              │
│  LLM ──calls tool──► AutoGen executes ──result──► LLM        │
│       ◄────────────────────────────────────────────  loop    │
│                      (until LLM stops calling tools)         │
└──────────────────────────────────────────────────────────────┘

Pipeline (sequential):

  Analyzer ──► Reviewer ──► Suggester ──► Summarizer
  (tools: 3)   (tools: 1)   (tools: 1)   (no tools)

Each agent's full text output is embedded in the next agent's
task prompt — context accumulates without a shared state object.
```

---

## Project Structure

```
code-review-autogen/
├── tools.py        # read_file, list_directory, get_file_stats
├── agents.py       # 4 × AssistantAgent with system prompts + tool registration
├── pipeline.py     # Sequential runner: run_pipeline() + _run_agent() streaming
├── cli.py          # Click CLI with Rich output (same UX as orchestra version)
├── config.py       # Ollama host + model via .env
├── .env.example
└── requirements.txt
```

---

## Setup

**1. Pull the model**

```bash
ollama pull llama3.2:3b
ollama serve          # keep running in a terminal
```

> **Better tool-calling models** (recommended for reliable results):
> ```bash
> ollama pull qwen2.5:7b    # excellent tool calling
> ollama pull llama3.1:8b   # strong tool calling
> ollama pull mistral:7b    # good tool calling
> ```
> Then set `AGENT_MODEL=qwen2.5:7b` in `.env`.

**2. Install dependencies**

```bash
cd code-review-autogen
pip install -r requirements.txt
```

**3. Configure (optional)**

```
configure `.env` as you like
# Edit AGENT_MODEL if using a different model
```

---

## Usage

### CLI

```bash
# Review a single file
python cli.py review /path/to/file.py

# Review a whole directory
python cli.py review /path/to/project/

# Print last saved report
python cli.py last

# Raw JSON output
python cli.py review /path/to/file.py --output json
```

### Web UI

```bash
uvicorn web.main:app --reload --port 8002
```

Open [http://localhost:8002](http://localhost:8002):

1. **Enter a path** manually, or click **📁 Browse** to open the file browser
2. Navigate directories, single-click to select, double-click to enter a folder
3. Use "Select this folder" to review an entire directory
4. Click **▶ Run Review** and watch the agentic loop stream live

**Pipeline log features:**
- Each agent stage is separated by a labelled divider
- Tool calls (LLM-requested, executed by AutoGen) appear dim + italic with a `⟳` prefix
- Timestamps on every line (`HH:MM:SS`)
- Colour-coded agent badges (blue / purple / green / yellow)
- Header note explains the AutoGen loop vs the context-gather pattern

---

## How Tool Calling Works Here

Each `AssistantAgent` is registered with tools:

```python
analyzer = AssistantAgent(
    name="Analyzer",
    model_client=OllamaClient(...),
    tools=[list_directory, read_file, get_file_stats],
    system_message="...",
    reflect_on_tool_use=True,   # re-reason after seeing results
)
```

AutoGen converts the Python functions into tool schemas automatically
(using type annotations and docstrings). When the LLM outputs a tool-call,
AutoGen executes the function and appends the result to the conversation —
no manual dispatch table needed.

Compare with the orchestra version:
```python
# orchestra/agents/analyzer.py — Python calls tools manually
content = read_file("/path/to/file.py")   # direct Python call
prompt  = f"Analyze this code:\n{content}\nReturn JSON."
raw     = self.chat([{"role": "user", "content": prompt}])
```

---

## Agent Outputs

| Agent | Key output fields |
|---|---|
| Analyzer | `files_analyzed`, `language`, `loc_total`, `functions`, `classes`, `complexity_notes` |
| Reviewer | `issues[]` (severity, category, location, evidence), `overall_risk` |
| Suggester | `improvements[]` (before/after snippets, priority), `quick_wins` |
| Summarizer | `overall_score` (0–100), `executive_summary`, `critical_findings` |

---

## Stack

- **LLM:** `llama3.2:3b` (or any Ollama model) via OpenAI-compatible endpoint
- **Agents:** [AutoGen `autogen-agentchat` v0.4](https://microsoft.github.io/autogen/)
- **Model client:** `autogen-ext[openai]` → `OpenAIChatCompletionClient`
- **CLI:** [Click](https://click.palletsprojects.com/) + [Rich](https://github.com/Textualize/rich)

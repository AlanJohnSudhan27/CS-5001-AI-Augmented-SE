# Code Review Pipeline — n8n

> **LLM Agent Orchestration Demo (n8n variant)** — CS 5001: AI-Augmented Software Engineering
> Missouri S&T

The same 4-agent code review pipeline, built as a **visual n8n workflow** instead of Python code.

---

## What this demonstrates

n8n is a no-code/low-code workflow automation tool. This shows how the same orchestration
pattern can be represented as a **visual graph** rather than imperative code.

| | Python (Orchestra / AutoGen) | n8n |
|---|---|---|
| **Orchestration** | Explicit Python loops | Visual node graph |
| **Agent calls** | `httpx` / AutoGen | HTTP Request nodes |
| **Data passing** | Function arguments | Node output → next node input |
| **Tool use** | Python functions / AutoGen | Not supported (HTTP Request only) |
| **Streaming** | SSE via FastAPI | Not natively supported |
| **Filesystem** | Direct | Only on self-hosted n8n |
| **Transparency** | Full code visibility | Each node shows its config |

---

## Workflow Structure

```
Webhook (POST /code-review)
    │
    ▼
Read Source Files        ← Code node: fs.readFileSync, up to 10 files
    │
    ▼
Analyzer                 ← HTTP Request → Ollama /api/chat
    │                       context: file content
    ▼
Reviewer                 ← HTTP Request → Ollama /api/chat
    │                       context: file content + Analyzer output
    ▼
Suggester                ← HTTP Request → Ollama /api/chat
    │                       context: file content + Analyzer + Reviewer output
    ▼
Summarizer               ← HTTP Request → Ollama /api/chat
    │                       context: all 3 previous outputs
    ▼
Build Report             ← Code node: parse JSON, assemble final report
    │
    ▼
Respond to Webhook       ← Returns JSON report
```

Each agent receives all previous agents' outputs in its prompt — the same
**accumulated context pattern** used in the Python versions.

---

## Setup

### 1. Install Node.js (if not already installed)

```bash
# Check first — need v18+
node --version

# Ubuntu/Debian: install Node 22 if needed
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### 2. Start Ollama

```bash
ollama serve
ollama pull llama3.2:3b
```

### 3. Start n8n

The `Read Source Files` Code node uses `require('fs')` to read files from disk.
n8n sandboxes Code nodes by default — you must explicitly allow `fs` and `path`:

```bash
# Required: allow filesystem access in Code nodes
NODE_FUNCTION_ALLOW_BUILTIN=fs,path npx n8n start

# Or install globally then use:
npm install -g n8n
NODE_FUNCTION_ALLOW_BUILTIN=fs,path n8n start
```

n8n opens at [http://localhost:5678](http://localhost:5678).
Create a free local account when prompted (stays on your machine).

> **Tip:** To use a different model, edit `workflow.json` and replace all four
> occurrences of `'llama3.2:3b'` with your model name (e.g. `'qwen2.5:7b'`),
> then re-import the file.

### 4. Import the workflow

1. Go to **Workflows** in the left sidebar
2. Click **+ New workflow**
3. Click the **⋮ menu** (top right of the canvas) → **Import from file**
4. Select `workflow.json` from this directory
5. Click **Save**
6. Toggle **Activate** (top right) to turn it on

### 5. Test it

```bash
curl -X POST http://localhost:5678/webhook/code-review \
  -H "Content-Type: application/json" \
  -d '{"path": "/absolute/path/to/file.py"}'
```

The response is the full JSON report.

---

## How the pipeline works in n8n

### Data flows as JSON between nodes

Every node outputs JSON. The next node reads it using n8n expressions:

```javascript
// In the Reviewer HTTP Request body:
$('Read Source Files').first().json.content    // file content from node 2
$('Analyzer').first().json.message.content    // LLM output from node 3
```

This is equivalent to passing structured data between Python functions.

### The HTTP Request nodes call Ollama directly

```
POST http://localhost:11434/api/chat
{
  "model": "llama3.2:3b",
  "messages": [
    { "role": "system", "content": "You are the Analyzer..." },
    { "role": "user",   "content": "Analyze this code: ..." }
  ],
  "stream": false,
  "format": "json"
}
```

### The Build Report Code node parses agent outputs

Since the LLM response is raw text (even with `format: json`), the Code node
uses the same 3-strategy JSON extraction as the Python versions:
1. Fenced code block (` ```json ... ``` `)
2. Whole text
3. Largest `{...}` substring

---

## Limitations vs Python versions

| Limitation | Reason |
|---|---|
| No real-time streaming | n8n returns the full response at the end |
| No tool calling | HTTP Request nodes send one prompt, get one response |
| Filesystem needs `NODE_FUNCTION_ALLOW_BUILTIN=fs,path` | n8n sandboxes Code nodes by default |
| Error messages are less descriptive | n8n error handling is less granular |
| Hard to unit-test | Workflow logic lives in the n8n UI, not source files |

---

## For the CS 5001 presentation

Use this alongside the Python versions to show the **same orchestration pattern
at three abstraction levels**:

| Level | Project | Orchestration |
|---|---|---|
| Low (explicit) | `code-review-orchestra` | Pure Python, manual loops |
| Mid (framework) | `code-review-autogen` | AutoGen `AssistantAgent` |
| High (visual) | `code-review-n8n` | n8n node graph |

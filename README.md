<<<<<<< HEAD
# CS-5001-AI-Augmented-SE
=======
# GitHub Review Agent

Ollama-powered CLI for reviewing git changes. The package now follows the same architecture style as `src/classroom_cli_agent`.

## Project Structure

```
github_agent/
  __init__.py
  agent.py
  cli.py
  llm.py
  prompts.py
  tools.py
  types.py
  utils.py
  analyzer.py
  categorizer.py
  reporter.py
  risk_assessor.py
  git_utils.py
```

Core flow is now:
- `cli.py` parses commands and builds config
- `agent.py` orchestrates analysis and reporting
- `tools.py` handles git interactions
- `llm.py` calls Ollama
- `prompts.py` defines model prompts
- `types.py` defines shared dataclasses
- `utils.py` handles validation and parsing helpers

## Requirements

- Python 3.7+
- Git
- Ollama installed and running
- Local Ollama model available (default: `llama3.1:8b`)

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Usage

### Review current branch

```bash
github-review --repo . branch
github-review --repo . branch --branch main
```

### Review commit range

```bash
github-review --repo . commits abc123..def456
```

### Alias command

```bash
github-review --repo . review
github-review --repo . review abc123..def456
```

### JSON output for CI

```bash
github-review --repo . --json branch
```

### Ollama options

```bash
github-review --repo . --model llama3.1:8b --host http://localhost:11434 --temperature 0.0 branch
```

You can also set:
- `OLLAMA_MODEL`
- `OLLAMA_HOST`
- `OLLAMA_TEMPERATURE`
>>>>>>> feature/new-feature

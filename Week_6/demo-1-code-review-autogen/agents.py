"""
AutoGen AssistantAgent definitions for the 4-stage code review pipeline.

Each agent is created fresh per pipeline run (factory functions) so that
conversation state doesn't bleed between runs.

Key difference from the Ollama version:
  Ollama version  → Python calls tools, builds prompt, one LLM call
  AutoGen version → LLM decides when to call tools; AutoGen executes them
                    and feeds results back (real agentic loop)
"""
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

import config
from tools import read_file, list_directory, get_file_stats


# ── Model client ───────────────────────────────────────────────

def _model_client() -> OpenAIChatCompletionClient:
    """Ollama via its OpenAI-compatible /v1 endpoint."""
    return OpenAIChatCompletionClient(
        model=config.MODEL,
        base_url=f"{config.OLLAMA_HOST}/v1",
        api_key="ollama",          # Ollama ignores the key; required by the client
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "structured_output": False,
            "family": "unknown",
        },
    )


# ── System prompts ─────────────────────────────────────────────

_ANALYZER_PROMPT = """\
You are the Analyzer — Stage 1 of a code review pipeline.

Use your tools to explore the target path:
1. Call list_directory to discover what source files exist
2. Call get_file_stats on interesting files to check their size/line count
3. Call read_file to read each source file (focus on .py .js .ts .go .rs .java)
   — examine up to 10 files

After reading the files, output a single JSON object with this exact structure:
{
  "files_analyzed": ["relative/path/file.py"],
  "language": "Python",
  "loc_total": 350,
  "functions": ["function_name_1", "function_name_2"],
  "classes": ["ClassName"],
  "imports": ["os", "sys"],
  "complexity_notes": ["Deep nesting in process_data()", "Long function main() — 80 lines"],
  "summary": "2-3 sentence overview of the codebase structure and purpose"
}

Output ONLY the JSON object — no prose before or after it.\
"""

_REVIEWER_PROMPT = """\
You are the Reviewer — Stage 2 of a code review pipeline.

You will receive the Analyzer's structural output plus the target path.
Use read_file to re-examine source files listed by the Analyzer.

Identify issues in these categories:
  bugs       — logical errors, off-by-one, incorrect behaviour
  security   — injection, auth bypass, exposed secrets, unsafe deserialization
  code_smell — duplicated code, god classes, dead code, magic numbers
  style      — naming inconsistency, missing docstrings, formatting

Severity levels: critical / high / medium / low

Output a single JSON object:
{
  "issues": [
    {
      "severity": "high",
      "category": "security",
      "description": "User input used directly in SQL query without parameterization",
      "location": "db.py:45",
      "evidence": "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')"
    }
  ],
  "overall_risk": "medium",
  "files_reviewed": ["db.py", "app.py"],
  "summary": "One paragraph summary of what was found"
}

Output ONLY the JSON object — no prose before or after it.\
"""

_SUGGESTER_PROMPT = """\
You are the Suggester — Stage 3 of a code review pipeline.

You will receive the Analyzer's structural map and the Reviewer's issue list.
Use read_file to re-read source files as needed.

For each significant issue propose a concrete fix ranked by impact (1 = highest).
Include short before/after code snippets (5–10 lines each).

Output a single JSON object:
{
  "improvements": [
    {
      "priority": 1,
      "title": "Parameterize SQL queries",
      "rationale": "Eliminates SQL injection risk entirely",
      "addresses_issue": "SQL injection in db.py:45",
      "before": "cursor.execute(f'SELECT * FROM users WHERE id={user_id}')",
      "after": "cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))"
    }
  ],
  "quick_wins": [
    "Add type hints to all function signatures",
    "Replace bare except: with except Exception as e:"
  ],
  "summary": "One paragraph summary of proposed improvements"
}

Output ONLY the JSON object — no prose before or after it.\
"""

_SUMMARIZER_PROMPT = """\
You are the Summarizer — the final stage of a code review pipeline.

You will receive the complete outputs from the Analyzer, Reviewer, and Suggester.
Synthesize these into a concise executive report with a quality score.

Score 0–100:
  90–100  Excellent — production-ready
  75–89   Good — minor polish needed
  60–74   Average — notable issues present
  40–59   Poor — significant rework needed
  0–39    Critical — major rework required

Scoring guide: start at 100, deduct:
  -15 per critical or high issue
  -5  per medium issue
  -10 if high complexity is noted
  -5  if error handling is missing

Output a single JSON object:
{
  "executive_summary": "2–3 sentences a non-technical manager could understand",
  "overall_score": 72,
  "critical_findings": [
    "SQL injection in db.py must be fixed before any public deployment"
  ],
  "top_improvements": [
    "Parameterize all database queries",
    "Add input validation at every API boundary"
  ]
}

Output ONLY the JSON object — no prose before or after it.\
"""


# ── Agent factories ────────────────────────────────────────────

def make_analyzer() -> AssistantAgent:
    return AssistantAgent(
        name="Analyzer",
        model_client=_model_client(),
        tools=[list_directory, read_file, get_file_stats],
        system_message=_ANALYZER_PROMPT,
        reflect_on_tool_use=True,   # Re-reason after seeing tool results
    )


def make_reviewer() -> AssistantAgent:
    return AssistantAgent(
        name="Reviewer",
        model_client=_model_client(),
        tools=[read_file],
        system_message=_REVIEWER_PROMPT,
        reflect_on_tool_use=True,
    )


def make_suggester() -> AssistantAgent:
    return AssistantAgent(
        name="Suggester",
        model_client=_model_client(),
        tools=[read_file],
        system_message=_SUGGESTER_PROMPT,
        reflect_on_tool_use=True,
    )


def make_summarizer() -> AssistantAgent:
    return AssistantAgent(
        name="Summarizer",
        model_client=_model_client(),
        tools=[],                   # No tools — synthesizes from context only
        system_message=_SUMMARIZER_PROMPT,
    )

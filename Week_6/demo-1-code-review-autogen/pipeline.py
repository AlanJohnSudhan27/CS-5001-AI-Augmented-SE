"""
Sequential 4-agent pipeline using AutoGen AssistantAgent.

Each agent runs its own agentic loop:
  1. LLM decides which tool to call
  2. AutoGen executes the tool
  3. Result is fed back to the LLM
  4. Loop until the LLM produces a final text response

The orchestrator then passes each agent's JSON output to the next agent
via the task prompt (accumulated context pattern).
"""
import asyncio
import inspect
import json
import re
from datetime import datetime, timezone
from typing import Callable, Optional

import config
from agents import make_analyzer, make_reviewer, make_suggester, make_summarizer


async def _emit(fn: Optional[Callable], agent: str, message: str) -> None:
    """Call emit whether it's a sync or async function. No-op if fn is None."""
    if fn is None:
        return
    result = fn(agent, message)
    if inspect.iscoroutine(result):
        await result


# ── JSON extraction ────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """
    Pull a JSON object from raw LLM output using three fallback strategies:
      1. Fenced code block  (```json ... ```)
      2. Whole text is valid JSON
      3. Largest {...} substring
    """
    # Strategy 1 — fenced block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2 — whole text
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 3 — largest {...} block
    best, depth, start = "", 0, -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                if len(candidate) > len(best):
                    best = candidate
    if best:
        try:
            return json.loads(best)
        except json.JSONDecodeError:
            pass

    return {}


# ── Single-agent runner ────────────────────────────────────────

async def _run_agent(
    agent,
    task: str,
    emit: Optional[Callable[[str, str], None]],
) -> tuple[str, dict]:
    """
    Run one agent to completion and return (raw_text, parsed_json).

    Streams events so the CLI/web can show tool calls in real time.
    """
    from autogen_agentchat.base import TaskResult

    raw_text = ""

    async for event in agent.run_stream(task=task):
        if isinstance(event, TaskResult):
            # Final message is the last TextMessage from this agent
            for msg in reversed(event.messages):
                src = getattr(msg, "source", "")
                content = getattr(msg, "content", "")
                if src == agent.name and isinstance(content, str):
                    raw_text = content
                    break
        elif hasattr(event, "source") and event.source == agent.name:
            content = getattr(event, "content", "")

            if isinstance(content, list):
                # Tool call request — show each call
                for item in content:
                    if hasattr(item, "name"):
                        args = getattr(item, "arguments", {})
                        path = (
                            args.get("path", "")
                            if isinstance(args, dict)
                            else str(args)[:60]
                        )
                        await _emit(emit, agent.name, f"[tool] {item.name}({path})")
            elif isinstance(content, str) and content.strip():
                # Intermediate text (reasoning before final response)
                first_line = content.strip().split("\n")[0][:140]
                if first_line and not first_line.lstrip().startswith("{"):
                    await _emit(emit, agent.name, first_line)

    parsed = _extract_json(raw_text)
    return raw_text, parsed


# ── Pipeline ───────────────────────────────────────────────────

async def run_pipeline(
    target_path: str,
    emit: Optional[Callable[[str, str], None]] = None,
) -> dict:
    """
    Run the 4-agent sequential code review pipeline.

    Context accumulates: each agent receives the prior agents' full
    text output embedded in its task prompt (no shared state object needed).
    """
    await _emit(emit, "Orchestrator", f"Target: {target_path}")

    # ── Stage 1: Analyzer ──────────────────────────────────────
    await _emit(emit, "Orchestrator", "Stage 1 / 4 — Analyzer")

    analyzer_text, analysis = await _run_agent(
        make_analyzer(),
        f"Analyze the code at this path: {target_path}",
        emit,
    )
    n = len(analysis.get("files_analyzed", []))
    await _emit(emit, "Orchestrator", f"Analyzer done — {n} file(s) examined")

    # ── Stage 2: Reviewer ──────────────────────────────────────
    await _emit(emit, "Orchestrator", "Stage 2 / 4 — Reviewer")

    reviewer_text, review = await _run_agent(
        make_reviewer(),
        (
            f"Review the code at: {target_path}\n\n"
            f"=== ANALYZER OUTPUT ===\n{analyzer_text}\n\n"
            "Use read_file to re-examine the source files listed above "
            "and identify all issues."
        ),
        emit,
    )
    n = len(review.get("issues", []))
    await _emit(emit, "Orchestrator", f"Reviewer done — {n} issue(s) identified")

    # ── Stage 3: Suggester ─────────────────────────────────────
    await _emit(emit, "Orchestrator", "Stage 3 / 4 — Suggester")

    suggester_text, suggestions = await _run_agent(
        make_suggester(),
        (
            f"Suggest improvements for the code at: {target_path}\n\n"
            f"=== ANALYZER OUTPUT ===\n{analyzer_text}\n\n"
            f"=== REVIEWER OUTPUT ===\n{reviewer_text}\n\n"
            "Use read_file to re-examine source files as needed."
        ),
        emit,
    )
    n = len(suggestions.get("improvements", []))
    await _emit(emit, "Orchestrator", f"Suggester done — {n} improvement(s) proposed")

    # ── Stage 4: Summarizer ────────────────────────────────────
    await _emit(emit, "Orchestrator", "Stage 4 / 4 — Summarizer")

    _, summary = await _run_agent(
        make_summarizer(),
        (
            f"Synthesize a final executive report for: {target_path}\n\n"
            f"=== ANALYZER OUTPUT ===\n{analyzer_text}\n\n"
            f"=== REVIEWER OUTPUT ===\n{reviewer_text}\n\n"
            f"=== SUGGESTER OUTPUT ===\n{suggester_text}"
        ),
        emit,
    )

    score = summary.get("overall_score", "?")
    await _emit(emit, "Orchestrator", f"Pipeline complete — score: {score}/100")

    # ── Assemble final report ──────────────────────────────────
    report = {
        "target_path": target_path,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": summary.get("overall_score", 50),
        "executive_summary": summary.get("executive_summary", ""),
        "critical_findings": summary.get("critical_findings", []),
        "top_improvements": summary.get("top_improvements", []),
        "analysis": analysis,
        "review": review,
        "suggestions": suggestions,
    }

    config.REPORT_FILE.write_text(json.dumps(report, indent=2))
    await _emit(emit, "Orchestrator", f"Saved → {config.REPORT_FILE.name}")

    return report


def run(target_path: str, emit: Optional[Callable[[str, str], None]] = None) -> dict:
    """Synchronous entry point — wraps run_pipeline for the CLI."""
    return asyncio.run(run_pipeline(target_path, emit))


def load_last_report() -> Optional[dict]:
    """Return the last saved report dict, or None if none exists."""
    if config.REPORT_FILE.exists():
        return json.loads(config.REPORT_FILE.read_text())
    return None

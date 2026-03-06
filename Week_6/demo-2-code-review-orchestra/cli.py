"""
Code Review Orchestra — CLI

Usage:
  python cli.py review <path>            # sequential pipeline
  python cli.py review <path> --parallel # parallel Reviewer+Suggester
  python cli.py last                     # print last saved report
"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from models.schemas import FinalReport
from orchestrator import Orchestrator, load_last_report

console = Console()

AGENT_COLORS = {
    "Analyzer":    "#58a6ff",
    "Reviewer":    "#bc8cff",
    "Suggester":   "#3fb950",
    "Summarizer":  "#e3b341",
    "Orchestrator": "white",
}

AGENT_ICONS = {
    "Analyzer":    "◎",
    "Reviewer":    "◎",
    "Suggester":   "◎",
    "Summarizer":  "◎",
    "Orchestrator": "·",
}

# Tracks which agent is currently active so we can print section headers
_current_agent: dict = {"name": None}


def _emit(agent: str, message: str) -> None:
    color = AGENT_COLORS.get(agent, "white")
    is_tool = message.startswith("[tool]")

    # Print a section header rule when a new pipeline agent starts
    if agent in ("Analyzer", "Reviewer", "Suggester", "Summarizer"):
        if agent != _current_agent["name"]:
            _current_agent["name"] = agent
            console.print()
            console.rule(
                f"[bold {color}] {agent} [/]",
                style=color,
                align="left",
            )
            console.print()

    if is_tool:
        # Tool calls: dim + italic so they read as "infrastructure"
        tool_part = message[len("[tool]"):].strip()
        console.print(f"    [dim italic]⟳ {tool_part}[/]")
    elif agent == "Orchestrator":
        console.print(f"  [dim]{message}[/]")
    else:
        console.print(f"  [{color}]▸[/] {message}")


# ── CLI group ──────────────────────────────────────────────────

@click.group()
def cli():
    """Code Review Orchestra — LLM Agent Orchestration Demo"""


# ── review command ─────────────────────────────────────────────

@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--parallel", is_flag=True, default=False,
    help="Run Reviewer and Suggester concurrently (stage 2+3 in parallel).",
)
@click.option(
    "--output", type=click.Choice(["rich", "json"]), default="rich",
    help="Output format.",
)
def review(path: str, parallel: bool, output: str) -> None:
    """Run the 4-agent code review pipeline on PATH."""
    _current_agent["name"] = None  # reset between runs

    console.print()
    console.print(
        Panel.fit(
            "[bold white]Code Review Orchestra[/]\n"
            "[dim]LLM Agent Orchestration Demo — CS 5001[/]",
            border_style="bright_blue",
        )
    )
    console.print()

    mode_label = (
        "[bold yellow]PARALLEL[/] (Reviewer + Suggester concurrent)"
        if parallel else "[bold cyan]SEQUENTIAL[/]"
    )
    console.print(f"  Mode:   {mode_label}")
    console.print(f"  Target: [bold]{path}[/]")
    console.print(f"  Model:  [dim]llama3.2:3b via Ollama[/]")
    console.print()
    console.rule("Pipeline", style="dim")

    try:
        report = Orchestrator().run(path, parallel=parallel, emit=_emit)
    except RuntimeError as exc:
        console.print(f"\n[bold red]Error:[/] {exc}")
        sys.exit(1)

    console.print()
    console.print()
    console.rule("Report", style="bright_blue")
    console.print()

    if output == "json":
        import json
        console.print_json(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report(report)


# ── last command ───────────────────────────────────────────────

@cli.command()
def last() -> None:
    """Print the most recently saved report."""
    report = load_last_report()
    if report is None:
        console.print("[yellow]No saved report found. Run `python cli.py review <path>` first.[/]")
        sys.exit(1)
    console.print()
    console.print(
        Panel.fit(
            f"[bold white]Last Report[/]\n"
            f"[dim]Target: {report.target_path}[/]\n"
            f"[dim]Generated: {report.generated_at}[/]",
            border_style="bright_blue",
        )
    )
    console.print()
    _print_report(report)


# ── Rich report renderer ───────────────────────────────────────

def _print_report(report: FinalReport) -> None:
    score = report.overall_score
    if score >= 90:
        score_color, grade = "bold green", "Excellent"
    elif score >= 75:
        score_color, grade = "bold cyan", "Good"
    elif score >= 60:
        score_color, grade = "bold yellow", "Average"
    elif score >= 40:
        score_color, grade = "bold red", "Poor"
    else:
        score_color, grade = "bold bright_red", "Critical"

    console.print(
        Panel(
            f"[{score_color}]{score}/100  {grade}[/]\n\n{report.executive_summary}",
            title="[bold]Executive Summary[/]",
            border_style="bright_blue",
        )
    )
    console.print()

    if report.critical_findings:
        console.print("[bold red]Critical Findings[/]")
        for f in report.critical_findings:
            console.print(f"  [red]●[/] {f}")
        console.print()

    if report.top_improvements:
        console.print("[bold green]Top Improvements[/]")
        for imp in report.top_improvements:
            console.print(f"  [green]●[/] {imp}")
        console.print()

    if report.review.issues:
        table = Table(
            title="Issues", show_header=True, header_style="bold white",
            border_style="dim", show_lines=True,
        )
        table.add_column("Sev", width=9)
        table.add_column("Cat", width=10)
        table.add_column("Location", width=26)
        table.add_column("Description")

        sev_colors = {"critical": "bright_red", "high": "red", "medium": "yellow", "low": "dim"}
        for issue in report.review.issues:
            c = sev_colors.get(issue.severity, "white")
            table.add_row(
                f"[{c}]{issue.severity}[/]",
                issue.category,
                issue.location,
                issue.description,
            )
        console.print(table)
        console.print()

    if report.suggestions.improvements:
        console.print("[bold #3fb950]Suggested Improvements[/]")
        for imp in sorted(report.suggestions.improvements, key=lambda x: x.priority):
            console.print(
                f"\n  [bold]#{imp.priority}  {imp.title}[/]"
                f"  [dim]→ {imp.addresses_issue}[/]"
            )
            console.print(f"  [dim]{imp.rationale}[/]")
            if imp.before:
                console.print("  [dim]Before:[/]")
                for line in imp.before.strip().splitlines():
                    console.print(f"    [red]{line}[/]")
            if imp.after:
                console.print("  [dim]After:[/]")
                for line in imp.after.strip().splitlines():
                    console.print(f"    [green]{line}[/]")
        console.print()

    if report.suggestions.quick_wins:
        console.print("[bold]Quick Wins[/]")
        for win in report.suggestions.quick_wins:
            console.print(f"  [cyan]→[/] {win}")
        console.print()

    console.print(
        Panel(
            f"[bold]Language:[/] {report.analysis.language}   "
            f"[bold]Files:[/] {len(report.analysis.files_analyzed)}   "
            f"[bold]LOC:[/] {report.analysis.loc_total}\n\n"
            + report.analysis.summary,
            title="[bold #58a6ff]Code Structure[/]",
            border_style="dim",
        )
    )
    console.print()


if __name__ == "__main__":
    cli()

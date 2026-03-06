"""
Code Review AutoGen — CLI

Usage:
  python cli.py review <path>   # run the 4-agent pipeline
  python cli.py last            # print the last saved report
"""
import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from pipeline import load_last_report, run

console = Console()

AGENT_COLORS = {
    "Analyzer":    "#58a6ff",
    "Reviewer":    "#bc8cff",
    "Suggester":   "#3fb950",
    "Summarizer":  "#e3b341",
    "Orchestrator": "white",
}

_current_agent: dict = {"name": None}


def _emit(agent: str, message: str) -> None:
    color = AGENT_COLORS.get(agent, "white")
    is_tool = message.startswith("[tool]")

    if agent in ("Analyzer", "Reviewer", "Suggester", "Summarizer"):
        if agent != _current_agent["name"]:
            _current_agent["name"] = agent
            console.print()
            console.rule(f"[bold {color}] {agent} [/]", style=color, align="left")
            console.print()

    if is_tool:
        tool_part = message[len("[tool]"):].strip()
        console.print(f"    [dim italic]⟳ {tool_part}[/]")
    elif agent == "Orchestrator":
        console.print(f"  [dim]{message}[/]")
    else:
        console.print(f"  [{color}]▸[/] {message}")


# ── CLI group ───────────────────────────────────────────────────

@click.group()
def cli():
    """Code Review AutoGen — AutoGen multi-agent demo"""


# ── review command ──────────────────────────────────────────────

@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", type=click.Choice(["rich", "json"]), default="rich")
def review(path: str, output: str) -> None:
    """Run the 4-agent AutoGen code review pipeline on PATH."""
    _current_agent["name"] = None

    console.print()
    console.print(
        Panel.fit(
            "[bold white]Code Review — AutoGen[/]\n"
            "[dim]Multi-Agent Demo — CS 5001[/]",
            border_style="bright_blue",
        )
    )
    console.print()
    console.print(f"  Target: [bold]{path}[/]")
    console.print(f"  Model:  [dim]{_model_name()}[/]")
    console.print()
    console.rule("Pipeline", style="dim")

    try:
        report = run(path, emit=_emit)
    except RuntimeError as exc:
        console.print(f"\n[bold red]Error:[/] {exc}")
        sys.exit(1)

    console.print()
    console.print()
    console.rule("Report", style="bright_blue")
    console.print()

    if output == "json":
        console.print_json(json.dumps(report, indent=2))
    else:
        _print_report(report)


# ── last command ────────────────────────────────────────────────

@cli.command()
def last() -> None:
    """Print the most recently saved report."""
    report = load_last_report()
    if report is None:
        console.print("[yellow]No saved report. Run `python cli.py review <path>` first.[/]")
        sys.exit(1)
    console.print()
    console.print(
        Panel.fit(
            f"[bold white]Last Report[/]\n"
            f"[dim]Target: {report.get('target_path', '?')}[/]\n"
            f"[dim]Generated: {report.get('generated_at', '?')}[/]",
            border_style="bright_blue",
        )
    )
    console.print()
    _print_report(report)


# ── helpers ─────────────────────────────────────────────────────

def _model_name() -> str:
    try:
        import config
        return f"{config.MODEL} via Ollama"
    except Exception:
        return "llama3.2:3b via Ollama"


def _print_report(report: dict) -> None:
    score = report.get("overall_score", 0)
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
            f"[{score_color}]{score}/100  {grade}[/]\n\n"
            + report.get("executive_summary", ""),
            title="[bold]Executive Summary[/]",
            border_style="bright_blue",
        )
    )
    console.print()

    findings = report.get("critical_findings", [])
    if findings:
        console.print("[bold red]Critical Findings[/]")
        for f in findings:
            console.print(f"  [red]●[/] {f}")
        console.print()

    improvements = report.get("top_improvements", [])
    if improvements:
        console.print("[bold green]Top Improvements[/]")
        for imp in improvements:
            console.print(f"  [green]●[/] {imp}")
        console.print()

    issues = report.get("review", {}).get("issues", [])
    if issues:
        table = Table(
            title="Issues", show_header=True, header_style="bold white",
            border_style="dim", show_lines=True,
        )
        table.add_column("Sev", width=9)
        table.add_column("Cat", width=10)
        table.add_column("Location", width=26)
        table.add_column("Description")

        sev_colors = {
            "critical": "bright_red", "high": "red",
            "medium": "yellow", "low": "dim",
        }
        for issue in issues:
            c = sev_colors.get(issue.get("severity", ""), "white")
            table.add_row(
                f"[{c}]{issue.get('severity', '')}[/]",
                issue.get("category", ""),
                issue.get("location", ""),
                issue.get("description", ""),
            )
        console.print(table)
        console.print()

    suggested = report.get("suggestions", {}).get("improvements", [])
    if suggested:
        console.print("[bold #3fb950]Suggested Improvements[/]")
        for imp in sorted(suggested, key=lambda x: x.get("priority", 99)):
            console.print(
                f"\n  [bold]#{imp.get('priority')}  {imp.get('title')}[/]"
                f"  [dim]→ {imp.get('addresses_issue', '')}[/]"
            )
            console.print(f"  [dim]{imp.get('rationale', '')}[/]")
            if imp.get("before"):
                console.print("  [dim]Before:[/]")
                for line in imp["before"].strip().splitlines():
                    console.print(f"    [red]{line}[/]")
            if imp.get("after"):
                console.print("  [dim]After:[/]")
                for line in imp["after"].strip().splitlines():
                    console.print(f"    [green]{line}[/]")
        console.print()

    quick_wins = report.get("suggestions", {}).get("quick_wins", [])
    if quick_wins:
        console.print("[bold]Quick Wins[/]")
        for win in quick_wins:
            console.print(f"  [cyan]→[/] {win}")
        console.print()

    analysis = report.get("analysis", {})
    console.print(
        Panel(
            f"[bold]Language:[/] {analysis.get('language', '?')}   "
            f"[bold]Files:[/] {len(analysis.get('files_analyzed', []))}   "
            f"[bold]LOC:[/] {analysis.get('loc_total', '?')}\n\n"
            + analysis.get("summary", ""),
            title="[bold #58a6ff]Code Structure[/]",
            border_style="dim",
        )
    )
    console.print()


if __name__ == "__main__":
    cli()

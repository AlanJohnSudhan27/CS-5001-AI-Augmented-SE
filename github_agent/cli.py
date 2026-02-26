"""CLI entry point for GitHub Review Agent."""

import sys
import click
from typing import Optional

from .git_utils import (
    is_git_repo,
    get_current_branch,
    get_default_branch,
    get_diff_from_branch,
    get_diff_from_commits,
    get_commit_messages,
)
from .analyzer import CodeAnalyzer
from .categorizer import ChangeCategorizer
from .risk_assessor import RiskAssessor
from .reporter import Reporter, determine_decision, ReviewDecision


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """GitHub Review Agent - Analyze and review git changes."""
    pass


@cli.command()
@click.option('--branch', '-b', help='Branch to compare against (default: main/master)')
@click.option('--no-colors', is_flag=True, help='Disable colored output')
def branch(branch: Optional[str], no_colors: bool):
    """Review changes in the current branch."""
    _review_branch(branch, not no_colors)


@cli.command()
@click.argument('commit_range')
@click.option('--no-colors', is_flag=True, help='Disable colored output')
def commits(commit_range: str, no_colors: bool):
    """Review changes in a commit range (format: start..end)."""
    _review_commits(commit_range, not no_colors)


def _review_branch(branch: Optional[str], use_colors: bool = True):
    """Review changes from current branch against default branch."""
    
    # Check if we're in a git repo
    if not is_git_repo():
        click.echo("Error: Not a git repository. Please run this command in a git repository.", err=True)
        sys.exit(1)
    
    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        click.echo("Error: Could not determine current branch.", err=True)
        sys.exit(1)
    
    # Get default branch if not specified
    if not branch:
        branch = get_default_branch()
    
    click.echo(f"Analyzing changes on branch '{current_branch}' vs '{branch}'...")
    
    # Get diff
    diff_result = get_diff_from_branch(branch)
    
    if not diff_result.files:
        click.echo("No changes found.")
        return
    
    # Analyze changes
    _perform_review(diff_result, use_colors)


def _review_commits(commit_range: str, use_colors: bool = True):
    """Review changes between commits."""
    
    # Check if we're in a git repo
    if not is_git_repo():
        click.echo("Error: Not a git repository. Please run this command in a git repository.", err=True)
        sys.exit(1)
    
    # Parse commit range
    if '..' not in commit_range:
        click.echo("Error: Commit range must be in format 'start..end'", err=True)
        sys.exit(1)
    
    parts = commit_range.split('..')
    if len(parts) != 2:
        click.echo("Error: Invalid commit range format. Use 'start..end'", err=True)
        sys.exit(1)
    
    start_commit, end_commit = parts[0].strip(), parts[1].strip()
    
    if not start_commit or not end_commit:
        click.echo("Error: Both start and end commits must be specified.", err=True)
        sys.exit(1)
    
    click.echo(f"Analyzing changes from {start_commit} to {end_commit}...")
    
    # Get diff
    diff_result = get_diff_from_commits(start_commit, end_commit)
    
    if not diff_result.files:
        click.echo("No changes found in the specified range.")
        return
    
    # Get commit messages
    commit_messages = get_commit_messages(start_commit, end_commit)
    
    # Analyze changes
    _perform_review(diff_result, use_colors, commit_messages)


def _perform_review(diff_result, use_colors: bool = True, commit_messages: list = None):
    """Perform the full review analysis."""
    
    # Initialize components
    analyzer = CodeAnalyzer()
    categorizer = ChangeCategorizer()
    risk_assessor = RiskAssessor()
    reporter = Reporter(use_colors=use_colors)
    
    # Analyze code for issues
    click.echo("Analyzing code changes...")
    issues = analyzer.analyze_diff(diff_result)
    
    # Categorize changes
    category = categorizer.categorize(diff_result, commit_messages)
    
    # Assess risk
    risk_assessment = risk_assessor.assess(diff_result, issues, category)
    
    # Determine decision
    decision, justification = determine_decision(risk_assessment, issues, category)
    
    # Print report
    reporter.print_review_report(
        diff_result=diff_result,
        issues=issues,
        category=category,
        risk_assessment=risk_assessment,
        decision=decision,
        justification=justification,
    )


# Alias for backward compatibility
@cli.command()
@click.argument('range', required=False)
@click.option('--branch', '-b', help='Branch to compare against')
@click.option('--no-colors', is_flag=True, help='Disable colored output')
def review(range: Optional[str], branch: Optional[str], no_colors: bool):
    """Review git changes (alias for branch/commits commands)."""
    if range:
        # It's a commit range
        _review_commits(range, not no_colors)
    else:
        # It's branch review
        _review_branch(branch, not no_colors)


if __name__ == '__main__':
    cli()

"""Reporter for formatting and displaying review results."""

from typing import List
from enum import Enum

from .git_utils import DiffResult
from .analyzer import Issue, IssueSeverity, IssueType
from .categorizer import ChangeCategory
from .risk_assessor import RiskLevel


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class ReviewDecision(Enum):
    """Possible review decisions."""
    CREATE_ISSUE = "create_issue"
    CREATE_PR = "create_pr"
    NO_ACTION = "no_action"


class Reporter:
    """Formats and displays review results."""
    
    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
    
    def print_review_report(
        self,
        diff_result: DiffResult,
        issues: List[Issue],
        category: ChangeCategory,
        risk_assessment,
        decision: ReviewDecision,
        justification: str,
    ):
        """Print a comprehensive review report."""
        self._print_header("Git Change Review Report")
        
        # Summary section
        self._print_summary(diff_result, category, risk_assessment)
        
        # Issues section
        self._print_issues(issues)
        
        # Risk assessment
        self._print_risk_assessment(risk_assessment)
        
        # Decision section
        self._print_decision(decision, justification)
        
        # File changes summary
        self._print_file_changes(diff_result)
    
    def _print_header(self, title: str):
        """Print a section header."""
        if self.use_colors:
            print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}{title.center(60)}{Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")
        else:
            print(f"\n{'=' * 60}")
            print(f"{title.center(60)}")
            print(f"{'=' * 60}\n")
    
    def _print_summary(self, diff_result: DiffResult, category: ChangeCategory, risk_assessment):
        """Print the summary section."""
        self._print_section_title("Summary")
        
        # Change stats
        print(f"  Files changed: {diff_result.total_files}")
        print(f"  Additions: {self._colorize(str(diff_result.total_additions), Colors.GREEN)}")
        print(f"  Deletions: {self._colorize(str(diff_result.total_deletions), Colors.RED)}")
        
        # Category
        print(f"\n  Category: {self._colorize(category.value.upper(), Colors.BLUE)}")
        
        # Risk level
        risk_color = self._get_risk_color(risk_assessment.level)
        print(f"  Risk Level: {self._colorize(risk_assessment.level.value.upper(), risk_color)}")
        
        print()
    
    def _print_issues(self, issues: List[Issue]):
        """Print detected issues."""
        self._print_section_title(f"Detected Issues ({len(issues)})")
        
        if not issues:
            print("  No issues detected.")
            print()
            return
        
        # Group by severity
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
        infos = [i for i in issues if i.severity == IssueSeverity.INFO]
        
        # Print errors first
        if errors:
            self._print_subsection(f"Errors ({len(errors)})", Colors.RED)
            for issue in errors:
                self._print_issue(issue, Colors.RED)
        
        if warnings:
            self._print_subsection(f"Warnings ({len(warnings)})", Colors.YELLOW)
            for issue in warnings:
                self._print_issue(issue, Colors.YELLOW)
        
        if infos:
            self._print_subsection(f"Info ({len(infos)})", Colors.GRAY)
            for issue in infos[:10]:  # Limit info items
                self._print_issue(issue, Colors.GRAY)
            if len(infos) > 10:
                print(f"  ... and {len(infos) - 10} more")
        
        print()
    
    def _print_issue(self, issue: Issue, color: str):
        """Print a single issue."""
        location = f"{issue.file_path}"
        if issue.line_number:
            location += f":{issue.line_number}"
        
        if self.use_colors:
            print(f"  {color}•{Colors.RESET} {issue.message}")
            print(f"    {Colors.GRAY}→ {location}{Colors.RESET}")
        else:
            print(f"  • {issue.message}")
            print(f"    → {location}")
        
        if issue.code_snippet:
            snippet = issue.code_snippet[:80] + "..." if len(issue.code_snippet) > 80 else issue.code_snippet
            if self.use_colors:
                print(f"    {Colors.GRAY}Code: {snippet}{Colors.RESET}")
            else:
                print(f"    Code: {snippet}")
    
    def _print_risk_assessment(self, risk_assessment):
        """Print risk assessment details."""
        self._print_section_title("Risk Assessment")
        
        print(f"  Score: {risk_assessment.score:.1f}")
        print(f"  Level: {self._colorize(risk_assessment.level.value.upper(), self._get_risk_color(risk_assessment.level))}")
        
        print("\n  Factors:")
        for factor in risk_assessment.factors:
            print(f"    • {factor}")
        
        print()
    
    def _print_decision(self, decision: ReviewDecision, justification: str):
        """Print the recommended decision."""
        self._print_section_title("Recommended Action")
        
        decision_text = {
            ReviewDecision.CREATE_ISSUE: "Create Issue",
            ReviewDecision.CREATE_PR: "Create Pull Request",
            ReviewDecision.NO_ACTION: "No Action Required",
        }
        
        decision_color = {
            ReviewDecision.CREATE_ISSUE: Colors.YELLOW,
            ReviewDecision.CREATE_PR: Colors.GREEN,
            ReviewDecision.NO_ACTION: Colors.BLUE,
        }
        
        print(f"  Action: {self._colorize(decision_text[decision], decision_color[decision])}")
        print(f"\n  Justification:")
        # Wrap justification text
        words = justification.split()
        line = "    "
        for word in words:
            if len(line) + len(word) > 55:
                print(line)
                line = "    " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)
        
        print()
    
    def _print_file_changes(self, diff_result: DiffResult):
        """Print summary of file changes."""
        self._print_section_title("File Changes")
        
        if not diff_result.files:
            print("  No files changed.")
            print()
            return
        
        # Show first 15 files
        for i, file_change in enumerate(diff_result.files[:15]):
            status_symbol = self._get_status_symbol(file_change.status)
            status_color = self._get_status_color(file_change.status)
            
            if self.use_colors:
                print(f"  {status_color}{status_symbol}{Colors.RESET} {file_change.path}")
            else:
                print(f"  {status_symbol} {file_change.path}")
            
            # Show additions/deletions
            if file_change.additions or file_change.deletions:
                add_str = f"+{file_change.additions}" if file_change.additions else ""
                del_str = f"-{file_change.deletions}" if file_change.deletions else ""
                stats = f"{add_str} {del_str}".strip()
                if self.use_colors:
                    print(f"      {Colors.GREEN}{add_str}{Colors.RESET} {Colors.RED}{del_str}{Colors.RESET}")
                else:
                    print(f"      {stats}")
        
        if len(diff_result.files) > 15:
            print(f"\n  ... and {len(diff_result.files) - 15} more files")
        
        print()
    
    def _print_section_title(self, title: str):
        """Print a section title."""
        if self.use_colors:
            print(f"{Colors.BOLD}{Colors.MAGENTA}--- {title} ---{Colors.RESET}")
        else:
            print(f"--- {title} ---")
    
    def _print_subsection(self, title: str, color: str):
        """Print a subsection title."""
        if self.use_colors:
            print(f"  {color}{title}{Colors.RESET}")
        else:
            print(f"  {title}")
    
    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if self.use_colors:
            return f"{color}{text}{Colors.RESET}"
        return text
    
    def _get_risk_color(self, risk_level: RiskLevel) -> str:
        """Get color for risk level."""
        colors = {
            RiskLevel.LOW: Colors.GREEN,
            RiskLevel.MEDIUM: Colors.YELLOW,
            RiskLevel.HIGH: Colors.RED,
        }
        return colors.get(risk_level, Colors.GRAY)
    
    def _get_status_symbol(self, status: str) -> str:
        """Get symbol for file status."""
        symbols = {
            'added': 'A',
            'modified': 'M',
            'deleted': 'D',
            'renamed': 'R',
        }
        return symbols.get(status, '?')
    
    def _get_status_color(self, status: str) -> str:
        """Get color for file status."""
        colors = {
            'added': Colors.GREEN,
            'modified': Colors.BLUE,
            'deleted': Colors.RED,
            'renamed': Colors.MAGENTA,
        }
        return colors.get(status, Colors.GRAY)


def determine_decision(
    risk_assessment,
    issues: List[Issue],
    category: ChangeCategory,
) -> tuple[ReviewDecision, str]:
    """Determine the recommended action based on analysis."""
    
    # Check for security issues - always recommend issue
    security_issues = [i for i in issues if i.issue_type == IssueType.SECURITY]
    if security_issues:
        evidence = f"Found {len(security_issues)} security issue(s): {security_issues[0].message}"
        return ReviewDecision.CREATE_ISSUE, evidence
    
    # High risk - recommend issue for discussion
    if risk_assessment.level == RiskLevel.HIGH:
        evidence = risk_assessment.justification
        return ReviewDecision.CREATE_ISSUE, evidence
    
    # Check for many errors
    errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
    if len(errors) >= 3:
        evidence = f"Found {len(errors)} critical errors that need attention"
        return ReviewDecision.CREATE_ISSUE, evidence
    
    # Documentation-only changes - no action needed
    if category == ChangeCategory.DOCUMENTATION:
        return ReviewDecision.NO_ACTION, "Documentation-only changes don't require action"
    
    # Style-only changes - no action needed
    if category == ChangeCategory.STYLE:
        return ReviewDecision.NO_ACTION, "Style-only changes don't require action"
    
    # Chore with no issues - no action needed
    if category == ChangeCategory.CHORE and not issues:
        return ReviewDecision.NO_ACTION, "Minor maintenance changes don't require action"
    
    # Default - recommend PR for ready changes
    if issues:
        evidence = f"Changes ready for review with {len(issues)} minor issue(s)"
    else:
        evidence = "Changes appear clean and ready for merge"
    
    return ReviewDecision.CREATE_PR, evidence

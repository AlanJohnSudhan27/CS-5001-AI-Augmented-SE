"""Code analyzer for detecting issues in changes."""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .git_utils import FileChange, DiffResult


class IssueSeverity(Enum):
    """Severity levels for issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueType(Enum):
    """Types of issues that can be detected."""
    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_SMELL = "code_smell"
    TODO = "todo"
    FIXME = "fixme"
    ERROR_HANDLING = "error_handling"


@dataclass
class Issue:
    """Represents a detected issue in the code."""
    severity: IssueSeverity
    issue_type: IssueType
    message: str
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    evidence: Optional[str] = None


class CodeAnalyzer:
    """Analyzes code changes for potential issues."""
    
    # Patterns for detecting various issues
    SECURITY_PATTERNS = [
        (r'password\s*=\s*["\"][^"\"]+["\"]', 'Hardcoded password detected'),
        (r'api[_-]?key\s*=\s*["\"][^"\"]+["\"]', 'Hardcoded API key detected'),
        (r'secret\s*=\s*["\"][^"\"]+["\"]', 'Hardcoded secret detected'),
        (r'token\s*=\s*["\"][^"\"]+["\"]', 'Hardcoded token detected'),
        (r'aws[_-]?access[_-]?key', 'AWS access key detected'),
        (r'execute\s*\(\s*["\"][^"\"]*\$\{', 'Potential command injection'),
        (r'eval\s*\(', 'Use of eval() is dangerous'),
        (r'exec\s*\(', 'Use of exec() is dangerous'),
        (r'__import__\s*\(\s*["\"][^"\"]+["\"]', 'Dynamic import detected'),
        (r'pickle\.load', 'Use of pickle.load is insecure'),
        (r'cPickle\.load', 'Use of cPickle.load is insecure'),
        (r'os\.system\s*\(', 'Use of os.system is dangerous'),
        (r'subprocess\.Popen', 'Use of subprocess.Popen may be dangerous'),
        (r'input\s*\(', 'Use of input() may be unsafe'),
        (r'open\s*\([^,]+,\s*["\"][wa][+]?b?["\"]', 'File opened for writing'),
        (r'\bmd5\b', 'Use of MD5 hash is insecure'),
        (r'\bsha1\b', 'Use of SHA1 hash is insecure'),
        (r'import\s+\*', 'Wildcard import detected'),
        (r'from\s+.+\s+import\s+\*', 'Wildcard import detected'),
        (r'\bhttp://', 'Use of insecure HTTP URL'),
        (r'\bassert\s+False', 'assert False detected'),
    ]

    BUG_PATTERNS = [
        (r'print\s*\(\s*debug', 'Debug print statement left in code'),
        (r'console\.log\s*\(.*debug', 'Debug console.log left in code'),
        (r'#\s*TODO.*bug', 'Known bug marked as TODO'),
        (r'pass\s*#.*not implemented', 'Not implemented code'),
        (r'\b/\s*0\b', 'Division by zero'),
        (r'\bNone\b\s*==', 'Possible None comparison bug'),
        (r'\bis\s+not\s+None', 'Explicit is not None check'),
        (r'\b==\s+None', 'Possible None comparison bug'),
        (r'\bexcept\s*:', 'Bare except clause - catches all exceptions'),
        (r'\bexcept\s+Exception\s*:', 'Catching Exception - may catch unexpected errors'),
        (r'try:.*except:.*pass', 'Empty except block'),
        (r'\bdel\s+\w+', 'Use of del statement'),
        (r'\bglobal\s+\w+', 'Use of global statement'),
        (r'\bexecfile\s*\(', 'Use of execfile() is dangerous'),
        (r'\binput\s*\(', 'Use of input() may be unsafe'),
    ]

    CODE_SMELL_PATTERNS = [
        (r'def\s+\w+\s*\([^)]*\):\s*\n\s*.{100,}', 'Function is too long (>100 chars)'),
        (r'class\s+\w+:\s*\n\s*def\s+\w+\s*\([^)]*\):\s*\n\s*def\s+\w+\s*\([^)]*\):', 'Multiple methods defined consecutively'),
        (r'print\s*\(\s*["\"].*%s.*["\"]', 'Use of printf-style formatting'),
        (r'for\s+\w+\s+in\s+\w+:\s*\n\s*\1\s*=\s*\1\s*\+\s*\w+', 'Manual sum loop, use sum()'),
        (r'\bpass\b\s*$', 'Pass statement (possible code smell)'),
        (r'\bcontinue\b\s*$', 'Continue statement (possible code smell)'),
        (r'\bbreak\b\s*$', 'Break statement (possible code smell)'),
        (r'\bprint\b\s*\(', 'Print statement (possible debug code)'),
        (r'\bassert\b\s+True', 'assert True detected'),
    ]

    TODO_FIXME_PATTERNS = [
        (r'#\s*TODO', 'TODO comment found'),
        (r'#\s*FIXME', 'FIXME comment found'),
        (r'#\s*HACK', 'HACK comment found'),
        (r'#\s*XXX', 'XXX comment found'),
        (r'#\s*BUG', 'BUG comment found'),
        (r'#\s*NOTE', 'NOTE comment found'),
    ]

    ERROR_HANDLING_PATTERNS = [
        (r'except\s*:', 'Bare except clause - catches all exceptions'),
        (r'except\s+Exception\s*:', 'Catching Exception - may catch unexpected errors'),
        (r'try:.*except:.*pass', 'Empty except block'),
        (r'return\s+None\s*#.*error', 'Returning None on error without raising'),
        (r'raise\s+Exception', 'Raising generic Exception'),
        (r'raise\s+\w+\(".*"\)', 'Raising exception with string message'),
        (r'\bpass\b\s*$', 'Pass statement in except block'),
    ]
    
    def __init__(self):
        self.issues: List[Issue] = []
    
    def analyze_diff(self, diff_result: DiffResult) -> List[Issue]:
        """Analyze all files in the diff result."""
        self.issues = []
        for file_change in diff_result.files:
            self.analyze_file(file_change)
            # Run flake8 on the file if possible (deep analysis)
            self.issues.extend(self._run_flake8(file_change))
        return self.issues

    def _run_flake8(self, file_change: FileChange) -> List[Issue]:
        """Run flake8 on the file if it exists on disk."""
        import subprocess
        import os
        issues = []
        # Only analyze .py files that exist
        if not file_change.path.endswith('.py'):
            return issues
        if not os.path.exists(file_change.path):
            return issues
        try:
            result = subprocess.run([
                'flake8', '--format=%(row)d:%(col)d:%(code)s:%(text)s', file_change.path
            ], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                try:
                    row, col, code, text = line.split(':', 3)
                    sev = IssueSeverity.ERROR if code.startswith('E') else IssueSeverity.WARNING
                    issues.append(Issue(
                        severity=sev,
                        issue_type=IssueType.CODE_SMELL,
                        message=f"flake8 {code}: {text.strip()}",
                        file_path=file_change.path,
                        line_number=int(row),
                        code_snippet=None,
                        evidence=f"flake8 at {row}:{col}"
                    ))
                except Exception:
                    continue
        except Exception:
            pass
        return issues
    
    def analyze_file(self, file_change: FileChange) -> List[Issue]:
        """Analyze a single file for issues (now scans full file content if available)."""
        file_issues = []
        # Skip certain file types
        if self._should_skip_file(file_change.path):
            return file_issues

        # Try to read the full file content from disk, fallback to diff content
        try:
            with open(file_change.path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            content = file_change.diff_content

        # Run all pattern checks on the full file content
        file_issues.extend(self._check_patterns(
            content,
            self.SECURITY_PATTERNS,
            IssueSeverity.ERROR,
            IssueType.SECURITY,
            file_change.path
        ))

        file_issues.extend(self._check_patterns(
            content,
            self.BUG_PATTERNS,
            IssueSeverity.WARNING,
            IssueType.BUG,
            file_change.path
        ))

        file_issues.extend(self._check_patterns(
            content,
            self.TODO_FIXME_PATTERNS,
            IssueSeverity.INFO,
            IssueType.TODO,
            file_change.path
        ))

        file_issues.extend(self._check_patterns(
            content,
            self.ERROR_HANDLING_PATTERNS,
            IssueSeverity.WARNING,
            IssueType.ERROR_HANDLING,
            file_change.path
        ))

        # Check for large files
        if file_change.additions > 500:
            file_issues.append(Issue(
                severity=IssueSeverity.WARNING,
                issue_type=IssueType.CODE_SMELL,
                message=f"Large file addition ({file_change.additions} lines)",
                file_path=file_change.path,
                evidence=f"File has {file_change.additions} additions"
            ))

        self.issues.extend(file_issues)
        return file_issues
    
    def _should_skip_file(self, filepath: str) -> bool:
        """Check if file should be skipped from analysis."""
        skip_extensions = [
            '.md', '.txt', '.rst', '.json', '.yaml', '.yml', 
            '.xml', '.csv', '.lock', '.min.js', '.min.css'
        ]
        
        skip_dirs = [
            'node_modules', 'vendor', 'dist', 'build', 
            '.git', '__pycache__', 'venv', '.venv'
        ]
        
        # Check extension
        for ext in skip_extensions:
            if filepath.endswith(ext):
                return True
        
        # Check directory
        parts = filepath.split('/')
        for part in parts:
            if part in skip_dirs:
                return True
        
        return False
    
    def _check_patterns(
        self,
        content: str,
        patterns: List[tuple],
        default_severity: IssueSeverity,
        default_type: IssueType,
        file_path: str
    ) -> List[Issue]:
        """Check content against a list of patterns."""
        issues = []
        lines = content.split('\n')
        
        for pattern, message in patterns:
            try:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(Issue(
                            severity=default_severity,
                            issue_type=default_type,
                            message=message,
                            file_path=file_path,
                            line_number=i,
                            code_snippet=line.strip()[:100],
                            evidence=f"Found at line {i}: {line.strip()[:100]}"
                        ))
            except re.error:
                # Skip invalid regex patterns
                continue
        
        return issues
    
    def get_issues_by_type(self, issue_type: IssueType) -> List[Issue]:
        """Get all issues of a specific type."""
        return [issue for issue in self.issues if issue.issue_type == issue_type]
    
    def get_issues_by_severity(self, severity: IssueSeverity) -> List[Issue]:
        """Get all issues of a specific severity."""
        return [issue for issue in self.issues if issue.severity == severity]

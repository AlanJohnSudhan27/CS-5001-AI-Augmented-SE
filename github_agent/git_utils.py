"""Git utilities for analyzing changes."""

import subprocess
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FileChange:
    """Represents a single file change."""
    path: str
    status: str  # 'added', 'modified', 'deleted', 'renamed'
    additions: int
    deletions: int
    diff_content: str


@dataclass
class DiffResult:
    """Represents the result of a git diff operation."""
    files: List[FileChange]
    total_additions: int
    total_deletions: int
    total_files: int


def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[str, str, int]:
    """Run a shell command and return stdout, stderr, and return code."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1


def get_current_branch() -> Optional[str]:
    """Get the current git branch."""
    stdout, _, rc = run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
    if rc == 0:
        return stdout.strip()
    return None


def get_default_branch() -> str:
    """Get the default branch (main or master)."""
    # Try main first
    stdout, _, rc = run_command(['git', 'rev-parse', '--verify', 'main'])
    if rc == 0:
        return 'main'
    
    # Try master
    stdout, _, rc = run_command(['git', 'rev-parse', '--verify', 'master'])
    if rc == 0:
        return 'master'
    
    # Fallback to origin/main
    return 'origin/main'


def get_diff_from_branch(branch: str) -> DiffResult:
    """Get diff between current branch and specified branch."""
    default_branch = get_default_branch()
    
    # Get diff stats
    stats_cmd = ['git', 'diff', '--stat', f'{default_branch}...HEAD']
    stdout, _, rc = run_command(stats_cmd)
    
    if rc != 0:
        # Try without the ... syntax if branch is ahead differently
        stdout, _, rc = run_command(['git', 'diff', '--stat', f'{default_branch}..HEAD'])
    
    files = []
    total_additions = 0
    total_deletions = 0
    
    # Parse the diff output to get file changes
    diff_cmd = ['git', 'diff', f'{default_branch}...HEAD', '--', '.']
    diff_output, _, _ = run_command(diff_cmd)
    
    if not diff_output:
        diff_cmd = ['git', 'diff', f'{default_branch}..HEAD', '--', '.']
        diff_output, _, _ = run_command(diff_cmd)
    
    files = parse_diff_output(diff_output)
    
    for f in files:
        total_additions += f.additions
        total_deletions += f.deletions
    
    return DiffResult(
        files=files,
        total_additions=total_additions,
        total_deletions=total_deletions,
        total_files=len(files)
    )


def get_diff_from_commits(start_commit: str, end_commit: str) -> DiffResult:
    """Get diff between two commits."""
    # Get diff stats
    stats_cmd = ['git', 'diff', '--stat', f'{start_commit}...{end_commit}']
    stdout, _, _ = run_command(stats_cmd)
    
    # Get full diff
    diff_cmd = ['git', 'diff', f'{start_commit}...{end_commit}', '--', '.']
    diff_output, _, _ = run_command(diff_cmd)
    
    if not diff_output:
        diff_cmd = ['git', 'diff', f'{start_commit}..{end_commit}', '--', '.']
        diff_output, _, _ = run_command(diff_cmd)
    
    files = parse_diff_output(diff_output)
    
    total_additions = sum(f.additions for f in files)
    total_deletions = sum(f.deletions for f in files)
    
    return DiffResult(
        files=files,
        total_additions=total_additions,
        total_deletions=total_deletions,
        total_files=len(files)
    )


def parse_diff_output(diff_output: str) -> List[FileChange]:
    """Parse git diff output into FileChange objects."""
    files = []
    current_file = None
    current_content = []
    file_stats = {}
    
    lines = diff_output.split('\n')
    
    # First pass: collect file stats from diff --stat
    stats_cmd = ['git', 'diff', '--stat']
    stats_output, _, _ = run_command(stats_cmd)
    
    for line in stats_output.split('\n'):
        if '|' in line:
            parts = line.split('|')
            if len(parts) >= 2:
                filepath = parts[0].strip()
                stats = parts[1].strip()
                # Parse something like " 100 +5 -3"
                additions = stats.count('+')
                deletions = stats.count('-')
                file_stats[filepath] = (additions, deletions)
    
    # Parse the actual diff
    current_path = None
    current_status = 'modified'
    diff_lines = []
    in_diff = False
    
    for line in lines:
        if line.startswith('diff --git'):
            if current_path:
                files.append(FileChange(
                    path=current_path,
                    status=current_status,
                    additions=file_stats.get(current_path, (0, 0))[0],
                    deletions=file_stats.get(current_path, (0, 0))[1],
                    diff_content='\n'.join(diff_lines)
                ))
            # Extract path from diff --git a/path b/path
            parts = line.replace('diff --git', '').strip().split()
            if len(parts) >= 2:
                # Get the 'b/' path (destination)
                current_path = parts[1].replace('b/', '') if 'b/' in parts[1] else parts[1]
            diff_lines = []
            in_diff = True
            current_status = 'modified'
            
        elif in_diff and line.startswith('new file'):
            current_status = 'added'
        elif in_diff and line.startswith('deleted file'):
            current_status = 'deleted'
        elif in_diff and line.startswith('rename from'):
            current_status = 'renamed'
        elif in_diff:
            diff_lines.append(line)
    
    # Add the last file
    if current_path:
        files.append(FileChange(
            path=current_path,
            status=current_status,
            additions=file_stats.get(current_path, (0, 0))[0],
            deletions=file_stats.get(current_path, (0, 0))[1],
            diff_content='\n'.join(diff_lines)
        ))
    
    return files


def get_commit_messages(start_commit: str, end_commit: str) -> List[str]:
    """Get commit messages between two commits."""
    cmd = ['git', 'log', f'{start_commit}...{end_commit}', '--pretty=format:%s']
    stdout, _, _ = run_command(cmd)
    return [msg.strip() for msg in stdout.split('\n') if msg.strip()]


def is_git_repo() -> bool:
    """Check if current directory is a git repository."""
    stdout, _, rc = run_command(['git', 'rev-parse', '--git-dir'])
    return rc == 0


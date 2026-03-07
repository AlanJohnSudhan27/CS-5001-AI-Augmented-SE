from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .git_utils import DiffResult, FileChange


class Tools:
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path.resolve()

    def run(self, args: list[str]) -> tuple[bool, str, str]:
        proc = subprocess.run(
            args,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            shell=False,
        )
        return proc.returncode == 0, (proc.stdout or ""), (proc.stderr or "")

    def is_git_repo(self) -> bool:
        ok, _, _ = self.run(["git", "rev-parse", "--git-dir"])
        return ok

    def current_branch(self) -> Optional[str]:
        ok, out, _ = self.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if not ok:
            return None
        value = out.strip()
        return value or None

    def default_branch(self) -> str:
        for name in ("main", "master"):
            ok, _, _ = self.run(["git", "rev-parse", "--verify", name])
            if ok:
                return name
        return "origin/main"

    def diff_from_branch(self, branch: Optional[str]) -> DiffResult:
        target = (branch or self.default_branch()).strip()
        revspec = f"{target}...HEAD"
        files = self._diff_files(revspec)
        if not files:
            files = self._diff_files(f"{target}..HEAD")

        return DiffResult(
            files=files,
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
            total_files=len(files),
        )

    def diff_from_commits(self, start_commit: str, end_commit: str) -> DiffResult:
        revspec = f"{start_commit}...{end_commit}"
        files = self._diff_files(revspec)
        if not files:
            files = self._diff_files(f"{start_commit}..{end_commit}")

        return DiffResult(
            files=files,
            total_additions=sum(f.additions for f in files),
            total_deletions=sum(f.deletions for f in files),
            total_files=len(files),
        )

    def commit_messages(self, start_commit: str, end_commit: str) -> list[str]:
        ok, out, _ = self.run(["git", "log", f"{start_commit}...{end_commit}", "--pretty=format:%s"])
        if not ok:
            ok, out, _ = self.run(["git", "log", f"{start_commit}..{end_commit}", "--pretty=format:%s"])
        if not ok:
            return []
        return [line.strip() for line in out.splitlines() if line.strip()]

    def _diff_files(self, revspec: str) -> list[FileChange]:
        patch_ok, patch_out, _ = self.run(["git", "diff", revspec, "--", "."])
        if not patch_ok:
            return []

        stats = self._numstat_map(revspec)
        files: list[FileChange] = []

        current_path: Optional[str] = None
        current_status = "modified"
        current_lines: list[str] = []

        for line in patch_out.splitlines():
            if line.startswith("diff --git "):
                if current_path:
                    add, delete = stats.get(current_path, (0, 0))
                    files.append(
                        FileChange(
                            path=current_path,
                            status=current_status,
                            additions=add,
                            deletions=delete,
                            diff_content="\n".join(current_lines),
                        )
                    )

                parts = line.split()
                if len(parts) >= 4:
                    b_path = parts[3]
                    current_path = b_path[2:] if b_path.startswith("b/") else b_path
                else:
                    current_path = None
                current_status = "modified"
                current_lines = []
                continue

            if current_path is None:
                continue

            if line.startswith("new file mode"):
                current_status = "added"
            elif line.startswith("deleted file mode"):
                current_status = "deleted"
            elif line.startswith("rename from") or line.startswith("rename to"):
                current_status = "renamed"

            current_lines.append(line)

        if current_path:
            add, delete = stats.get(current_path, (0, 0))
            files.append(
                FileChange(
                    path=current_path,
                    status=current_status,
                    additions=add,
                    deletions=delete,
                    diff_content="\n".join(current_lines),
                )
            )

        return files

    def _numstat_map(self, revspec: str) -> dict[str, tuple[int, int]]:
        ok, out, _ = self.run(["git", "diff", "--numstat", revspec, "--", "."])
        if not ok:
            return {}

        mapped: dict[str, tuple[int, int]] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue

            add_raw, del_raw, path_raw = parts[0].strip(), parts[1].strip(), parts[-1].strip()
            try:
                additions = int(add_raw) if add_raw != "-" else 0
                deletions = int(del_raw) if del_raw != "-" else 0
            except ValueError:
                continue

            mapped[path_raw] = (additions, deletions)

        return mapped

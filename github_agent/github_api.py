from __future__ import annotations

from typing import List, Optional

import requests


class GitHubAPIError(Exception):
    pass


class GitHubAPI:
    """GitHub REST API v3 client.

    Tool Use Pattern: provides real GitHub data fetching and creation.
    No content is fabricated — all data comes from the live API.
    """

    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.request(method, url, timeout=30, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise GitHubAPIError(f"Network error calling {url}: {exc}") from exc
        if resp.status_code == 204:
            return {}
        if not resp.ok:
            raise GitHubAPIError(
                f"GitHub API {method} {url} -> {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_repo_info(self, owner: str, repo: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}")

    def get_issue(self, owner: str, repo: str, issue_num: int) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_num}")

    def get_pr(self, owner: str, repo: str, pr_num: int) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_num}")

    # ------------------------------------------------------------------
    # Write operations (require human approval before being called)
    # ------------------------------------------------------------------

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> dict:
        payload: dict = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        return self._request("POST", f"/repos/{owner}/{repo}/issues", json=payload)

    def create_pr(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict:
        payload = {"title": title, "body": body, "head": head, "base": base}
        return self._request("POST", f"/repos/{owner}/{repo}/pulls", json=payload)

    def add_comment(
        self,
        owner: str,
        repo: str,
        issue_or_pr_num: int,
        body: str,
    ) -> dict:
        """Add a comment to an issue or PR (PRs use the issues comments endpoint)."""
        return self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{issue_or_pr_num}/comments",
            json={"body": body},
        )

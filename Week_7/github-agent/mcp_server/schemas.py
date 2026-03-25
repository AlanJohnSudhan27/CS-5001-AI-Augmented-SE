"""
Tool schemas — the only place tool names, descriptions, and parameter
shapes are defined. mcp_server/app.py and mcp_server/handlers.py both derive
from this file; nothing else needs to change when a tool is added.
"""

TOOLS = [
    {
        "name": "git_diff",
        "description": "Get the git diff for working tree changes or a commit range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the git repository"},
                "commit_range": {
                    "type": "string",
                    "description": "Optional commit range (e.g. 'HEAD~3..HEAD'). Omit for working tree diff.",
                },
            },
            "required": ["repo_path"],
        },
    },
    {
        "name": "git_log",
        "description": "Get recent git log entries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the git repository"},
                "max_count": {"type": "integer", "description": "Max commits to show (default 10)"},
            },
            "required": ["repo_path"],
        },
    },
    {
        "name": "git_show",
        "description": "Show the full details of a specific commit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Path to the git repository"},
                "commit_sha": {"type": "string", "description": "Commit SHA to show"},
            },
            "required": ["repo_path", "commit_sha"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the content of a source file (capped at 8000 chars).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and subdirectories inside a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "grep_code",
        "description": "Search for a text pattern inside source files under a directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search term or regex"},
                "path": {"type": "string", "description": "Root directory to search"},
            },
            "required": ["pattern", "path"],
        },
    },
    {
        "name": "github_get_issue",
        "description": "Fetch an existing GitHub issue by number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "issue_number": {"type": "integer", "description": "Issue number"},
            },
            "required": ["owner", "repo", "issue_number"],
        },
    },
    {
        "name": "github_get_pr",
        "description": "Fetch an existing GitHub pull request by number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "pr_number": {"type": "integer", "description": "Pull request number"},
            },
            "required": ["owner", "repo", "pr_number"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a new GitHub issue.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue body (Markdown)"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional labels",
                },
            },
            "required": ["owner", "repo", "title", "body"],
        },
    },
    {
        "name": "github_create_pr",
        "description": "Create a new GitHub pull request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR body (Markdown)"},
                "head": {"type": "string", "description": "Head branch name"},
                "base": {"type": "string", "description": "Base branch name"},
            },
            "required": ["owner", "repo", "title", "body", "head", "base"],
        },
    },
]

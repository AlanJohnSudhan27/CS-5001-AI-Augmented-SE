"""
Pydantic models for the web API request/response bodies.
"""
from pydantic import BaseModel


class ReviewRequest(BaseModel):
    repo_source: str             # local path OR GitHub URL
    commit_range: str = ""


class DraftRequest(BaseModel):
    mode: str = "from_instruction"     # "from_instruction" | "from_review"
    action_type: str = "issue"         # "issue" | "pr"
    repo_source: str = "."             # local path OR GitHub URL
    commit_range: str = ""
    instruction: str = ""
    review_context: str = ""
    owner: str = ""
    repo: str = ""
    head: str = ""
    base: str = "main"


class ImproveRequest(BaseModel):
    repo_source: str                   # GitHub URL or "owner/repo"
    number: int
    item_type: str = "issue"           # "issue" | "pr"

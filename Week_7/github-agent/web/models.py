"""
Pydantic models for the web API request/response bodies.
"""
from pydantic import BaseModel


class ReviewRequest(BaseModel):
    commit_range: str = ""


class DraftRequest(BaseModel):
    mode: str = "from_instruction"     # "from_instruction" | "from_review"
    action_type: str = "issue"         # "issue" | "pr"
    commit_range: str = ""
    instruction: str = ""
    review_context: str = ""
    owner: str = ""
    repo: str = ""
    head: str = ""
    base: str = "main"


class ImproveRequest(BaseModel):
    owner: str
    repo: str
    number: int
    item_type: str = "issue"           # "issue" | "pr"

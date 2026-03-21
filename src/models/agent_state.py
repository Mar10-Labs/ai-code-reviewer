from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone

from src.models.review_comment import ReviewComment
from src.models.file_context import EnrichedFileContext


def utc_now():
    return datetime.now(timezone.utc)


class EnrichedDiff(BaseModel):
    file_path: str
    language: str
    diff_content: str
    num_additions: int
    num_deletions: int
    chunks: list[str] = Field(default_factory=list)
    file_context: Optional[EnrichedFileContext] = None


class AgentState(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pr_id": 123,
                "pr_title": "feat: add user authentication",
                "repository": "owner/repo",
                "status": "processing"
            }
        }
    )
    
    pr_id: int
    pr_title: str
    repository: str
    current_file: Optional[str] = None
    enriched_diffs: list[EnrichedDiff] = Field(default_factory=list)
    enriched_contexts: list[EnrichedFileContext] = Field(default_factory=list)
    review_comments: list[ReviewComment] = Field(default_factory=list)
    agent_name: Optional[str] = None
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

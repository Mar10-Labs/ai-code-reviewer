from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


class ReviewComment(BaseModel):
    file_path: str
    line_number: int
    severity: Literal["critical", "warning", "suggestion"]
    category: Literal["security", "performance", "quality", "debt", "tests"]
    comment: str = Field(min_length=20, max_length=500)
    suggested_fix: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class EnrichedDiff(BaseModel):
    file_path: str
    language: str
    diff_content: str
    num_additions: int
    num_deletions: int
    chunks: list[str] = Field(default_factory=list)


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
    review_comments: list[ReviewComment] = Field(default_factory=list)
    agent_name: Optional[str] = None
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

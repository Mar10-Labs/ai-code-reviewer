from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


class SeverityLevel(str):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class CategoryType(str):
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    DEBT = "debt"
    TESTS = "tests"
    ARCHITECTURE = "architecture"
    STYLE = "style"
    DOCS = "docs"


class ReviewComment(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "file_path": "src/api/main.py",
                "line_number": 42,
                "severity": "warning",
                "category": "security",
                "comment": "This function does not validate input parameters, which could lead to SQL injection attacks.",
                "suggested_fix": "Add input validation using Pydantic schemas before processing.",
                "confidence": 0.85
            }
        }
    )
    
    file_path: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Path to the file being reviewed"
    )
    
    line_number: int = Field(
        ...,
        ge=1,
        le=1000000,
        description="Line number where the comment applies"
    )
    
    severity: Literal["critical", "warning", "suggestion"] = Field(
        ...,
        description="Severity level of the review comment"
    )
    
    category: Literal[
        "security", 
        "performance", 
        "quality", 
        "debt", 
        "tests",
        "architecture",
        "style",
        "docs"
    ] = Field(
        ...,
        description="Category of the review comment"
    )
    
    comment: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="The review comment text"
    )
    
    suggested_fix: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional suggested fix for the issue"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1"
    )
    
    agent_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Name of the agent that generated this comment"
    )
    
    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if v.startswith(" "):
            raise ValueError("file_path cannot start with whitespace")
        if ".." in v:
            raise ValueError("file_path cannot contain '..' for security")
        if not re.match(r'^[a-zA-Z0-9_\-./\\]+$', v):
            raise ValueError("file_path contains invalid characters")
        return v
    
    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: str) -> str:
        if v.strip() != v:
            raise ValueError("comment cannot have leading/trailing whitespace")
        if len(v.split()) < 4:
            raise ValueError("comment must contain at least 4 words")
        return v
    
    @field_validator("line_number")
    @classmethod
    def validate_line_number(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("line_number must be positive")
        return v


class ReviewCommentCollection(BaseModel):
    comments: list[ReviewComment] = Field(default_factory=list)
    total_count: int = Field(default=0)
    
    @field_validator("total_count")
    @classmethod
    def validate_count(cls, v: int, info) -> int:
        if "comments" in info.data and len(info.data["comments"]) != v:
            raise ValueError("total_count must match length of comments")
        return v


class SeveritySummary(BaseModel):
    critical: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    suggestion: int = Field(default=0, ge=0)
    
    @property
    def total(self) -> int:
        return self.critical + self.warning + self.suggestion
    
    def to_dict(self) -> dict[str, int]:
        return {
            "critical": self.critical,
            "warning": self.warning,
            "suggestion": self.suggestion,
            "total": self.total
        }


def summarize_by_severity(comments: list[ReviewComment]) -> SeveritySummary:
    summary = SeveritySummary()
    for comment in comments:
        if comment.severity == "critical":
            summary.critical += 1
        elif comment.severity == "warning":
            summary.warning += 1
        else:
            summary.suggestion += 1
    return summary

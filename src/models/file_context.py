from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class FileChange(BaseModel):
    date: datetime
    message: str
    author: str
    lines_changed: int


class FileContext(BaseModel):
    file_path: str
    language: str
    current_content: Optional[str] = None
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    public_api: list[str] = Field(default_factory=list)
    change_history: list[FileChange] = Field(default_factory=list)
    is_interface_file: bool = False
    is_critical: bool = False


class EnrichedFileContext(BaseModel):
    file_context: FileContext
    related_files: list[FileContext] = Field(default_factory=list)
    dependency_impact: list[str] = Field(default_factory=list)
    breaking_change_detected: bool = False
    analysis_notes: list[str] = Field(default_factory=list)

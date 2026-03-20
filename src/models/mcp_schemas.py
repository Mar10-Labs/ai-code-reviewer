from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class FileContextRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={
            "example": {
                "file_path": "src/api/main.py",
                "start_line": 1,
                "end_line": 50,
                "include_context": True
            }
        }
    )
    
    file_path: str = Field(..., min_length=1, max_length=500)
    start_line: int = Field(default=1, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)
    include_context: bool = Field(default=True)
    max_lines: int = Field(default=100, ge=1, le=500)


class FileContextResponse(BaseModel):
    file_path: str
    language: Optional[str] = None
    content: str
    start_line: int
    end_line: int
    total_lines: int
    truncated: bool = False
    context_lines_before: int = 0
    context_lines_after: int = 0


class RepoStructureRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path": "src",
                "max_depth": 3,
                "include_files": True,
                "exclude_patterns": ["__pycache__", "*.pyc", ".git"]
            }
        }
    )
    
    path: str = Field(default=".", min_length=1)
    max_depth: int = Field(default=3, ge=1, le=10)
    include_files: bool = Field(default=True)
    exclude_patterns: list[str] = Field(
        default=["__pycache__", "*.pyc", ".git", ".venv", "node_modules", ".pytest_cache"],
        max_length=20
    )
    include_hidden: bool = Field(default=False)


class FileNode(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None
    modified_at: Optional[datetime] = None
    children: Optional[list["FileNode"]] = None


class RepoStructureResponse(BaseModel):
    root_path: str
    total_files: int = 0
    total_directories: int = 0
    structure: list[FileNode]
    languages: dict[str, int] = Field(default_factory=dict)


class FunctionDefinitionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_path": "src/api/main.py",
                "function_name": "health_check",
                "include_calls": True,
                "include_docstring": True
            }
        }
    )
    
    file_path: str = Field(..., min_length=1, max_length=500)
    function_name: str = Field(..., min_length=1, max_length=100)
    include_calls: bool = Field(default=True)
    include_docstring: bool = Field(default=True)
    max_depth: int = Field(default=2, ge=1, le=5)


class ParameterInfo(BaseModel):
    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = True


class FunctionDefinition(BaseModel):
    name: str
    file_path: str
    line_number: int
    parameters: list[ParameterInfo] = Field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    decorators: list[str] = Field(default_factory=list)
    called_functions: list[str] = Field(default_factory=list)
    complexity_score: Optional[int] = None


class FunctionDefinitionResponse(BaseModel):
    function: FunctionDefinition
    related_functions: list[FunctionDefinition] = Field(default_factory=list)
    calls_count: int = 0


class MCPToolRequest(BaseModel):
    tool_name: Literal["get_file_context", "list_repo_structure", "get_function_definition"]
    parameters: dict


class MCPToolResponse(BaseModel):
    tool_name: str
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    execution_time_ms: float


class MCPSessionState(BaseModel):
    session_id: str
    started_at: datetime
    last_accessed: datetime
    files_accessed: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    context_window_usage: float = Field(default=0.0, ge=0.0, le=1.0)

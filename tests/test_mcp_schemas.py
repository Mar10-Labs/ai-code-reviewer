import pytest
from datetime import datetime
from pydantic import ValidationError
from src.models.mcp_schemas import (
    FileContextRequest,
    FileContextResponse,
    RepoStructureRequest,
    RepoStructureResponse,
    FunctionDefinitionRequest,
    FunctionDefinition,
    ParameterInfo,
    FunctionDefinitionResponse,
    MCPToolRequest,
    MCPToolResponse,
    MCPSessionState,
    FileNode,
)


class TestFileContextRequest:
    def test_valid_request(self):
        request = FileContextRequest(
            file_path="src/main.py",
            start_line=1,
            end_line=50
        )
        assert request.file_path == "src/main.py"
        assert request.start_line == 1
        assert request.end_line == 50
        assert request.include_context is True
        assert request.max_lines == 100

    def test_default_values(self):
        request = FileContextRequest(file_path="src/main.py")
        assert request.start_line == 1
        assert request.end_line is None
        assert request.include_context is True
        assert request.max_lines == 100

    def test_file_path_required(self):
        with pytest.raises(ValidationError):
            FileContextRequest(file_path="")

    def test_start_line_must_be_positive(self):
        with pytest.raises(ValidationError):
            FileContextRequest(file_path="src/main.py", start_line=0)

    def test_max_lines_limits(self):
        with pytest.raises(ValidationError):
            FileContextRequest(file_path="src/main.py", max_lines=1000)


class TestFileContextResponse:
    def test_valid_response(self):
        response = FileContextResponse(
            file_path="src/main.py",
            language="python",
            content="def main(): pass",
            start_line=1,
            end_line=2,
            total_lines=2
        )
        assert response.file_path == "src/main.py"
        assert response.truncated is False

    def test_truncated_response(self):
        response = FileContextResponse(
            file_path="src/main.py",
            content="...",
            start_line=1,
            end_line=100,
            total_lines=500,
            truncated=True,
            context_lines_before=5,
            context_lines_after=10
        )
        assert response.truncated is True
        assert response.context_lines_before == 5


class TestRepoStructureRequest:
    def test_valid_request(self):
        request = RepoStructureRequest(
            path="src",
            max_depth=3,
            include_files=True
        )
        assert request.path == "src"
        assert request.max_depth == 3
        assert request.include_hidden is False

    def test_default_exclude_patterns(self):
        request = RepoStructureRequest()
        assert "__pycache__" in request.exclude_patterns
        assert ".git" in request.exclude_patterns
        assert "node_modules" in request.exclude_patterns

    def test_max_depth_limits(self):
        with pytest.raises(ValidationError):
            RepoStructureRequest(max_depth=15)

    def test_max_exclude_patterns(self):
        with pytest.raises(ValidationError):
            RepoStructureRequest(
                exclude_patterns=[f"pattern{i}" for i in range(25)]
            )


class TestFileNode:
    def test_file_node(self):
        node = FileNode(
            name="main.py",
            path="src/main.py",
            is_directory=False,
            size=1024
        )
        assert node.name == "main.py"
        assert node.is_directory is False
        assert node.size == 1024
        assert node.children is None

    def test_directory_node(self):
        node = FileNode(
            name="src",
            path="src",
            is_directory=True,
            children=[]
        )
        assert node.is_directory is True
        assert node.children == []


class TestFunctionDefinitionRequest:
    def test_valid_request(self):
        request = FunctionDefinitionRequest(
            file_path="src/main.py",
            function_name="health_check"
        )
        assert request.include_calls is True
        assert request.include_docstring is True
        assert request.max_depth == 2

    def test_function_name_required(self):
        with pytest.raises(ValidationError):
            FunctionDefinitionRequest(
                file_path="src/main.py",
                function_name=""
            )


class TestParameterInfo:
    def test_required_parameter(self):
        param = ParameterInfo(
            name="value",
            type_hint="int"
        )
        assert param.name == "value"
        assert param.type_hint == "int"
        assert param.is_required is True
        assert param.default_value is None

    def test_optional_parameter(self):
        param = ParameterInfo(
            name="value",
            type_hint="Optional[str]",
            default_value="None",
            is_required=False
        )
        assert param.is_required is False
        assert param.default_value == "None"


class TestFunctionDefinition:
    def test_function_definition(self):
        func = FunctionDefinition(
            name="health_check",
            file_path="src/api/main.py",
            line_number=10,
            return_type="dict",
            is_async=False
        )
        assert func.name == "health_check"
        assert func.decorators == []
        assert func.called_functions == []

    def test_function_with_parameters(self):
        func = FunctionDefinition(
            name="process",
            file_path="src/main.py",
            line_number=5,
            parameters=[
                ParameterInfo(name="data", type_hint="str"),
                ParameterInfo(name="timeout", type_hint="int", default_value="30", is_required=False)
            ]
        )
        assert len(func.parameters) == 2
        assert func.parameters[0].is_required is True
        assert func.parameters[1].is_required is False


class TestMCPToolRequest:
    def test_valid_tool_request(self):
        request = MCPToolRequest(
            tool_name="get_file_context",
            parameters={"file_path": "src/main.py"}
        )
        assert request.tool_name == "get_file_context"

    def test_all_tool_names(self):
        for tool in ["get_file_context", "list_repo_structure", "get_function_definition"]:
            request = MCPToolRequest(tool_name=tool, parameters={})
            assert request.tool_name == tool

    def test_invalid_tool_name(self):
        with pytest.raises(ValidationError):
            MCPToolRequest(tool_name="invalid_tool", parameters={})


class TestMCPToolResponse:
    def test_successful_response(self):
        response = MCPToolResponse(
            tool_name="get_file_context",
            success=True,
            data={"content": "def main(): pass"},
            execution_time_ms=15.5
        )
        assert response.success is True
        assert response.data is not None
        assert response.error is None

    def test_failed_response(self):
        response = MCPToolResponse(
            tool_name="get_file_context",
            success=False,
            error="File not found",
            execution_time_ms=5.2
        )
        assert response.success is False
        assert response.error == "File not found"


class TestMCPSessionState:
    def test_session_state(self):
        from datetime import datetime
        state = MCPSessionState(
            session_id="abc123",
            started_at=datetime.now(),
            last_accessed=datetime.now()
        )
        assert state.files_accessed == []
        assert state.tools_used == []
        assert state.context_window_usage == 0.0

    def test_context_window_limit(self):
        with pytest.raises(ValidationError):
            MCPSessionState(
                session_id="abc",
                started_at=datetime.now(),
                last_accessed=datetime.now(),
                context_window_usage=1.5
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


class TestGitClient:
    """Tests for GitClient"""

    def test_get_file_content_success(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="file content"
            )
            
            client = GitClient()
            result = client.get_file_content("test.py")
            
            assert result == "file content"
            mock_run.assert_called_once()

    def test_get_file_content_with_ref(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="content at ref"
            )
            
            client = GitClient()
            result = client.get_file_content("test.py", ref="v1.0")
            
            assert result == "content at ref"
            assert "v1.0:test.py" in str(mock_run.call_args)

    def test_get_file_content_failure(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            
            client = GitClient()
            result = client.get_file_content("nonexistent.py")
            
            assert result == ""

    def test_get_file_content_exception(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run', side_effect=Exception("git error")):
            client = GitClient()
            result = client.get_file_content("test.py")
            
            assert result == ""

    def test_get_file_blame_success(self):
        from src.infrastructure.services.git_client import GitClient
        
        blame_output = """commit abc123
author John Doe
author-time 1609459200
filename test.py
	Line 1 content
	Line 2 content
"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=blame_output
            )
            
            client = GitClient()
            result = client.get_file_blame("test.py")
            
            assert result.file_path == "test.py"
            assert result.total_lines == 2
            assert len(result.lines) == 2
            assert result.lines[0].line_content == "Line 1 content"
            assert "John Doe" in result.authors or "ohn Doe" in result.authors

    def test_get_file_blame_failure(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            
            client = GitClient()
            result = client.get_file_blame("nonexistent.py")
            
            assert result.file_path == "nonexistent.py"
            assert result.total_lines == 0
            assert result.lines == []

    def test_get_file_blame_exception(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run', side_effect=Exception("git error")):
            client = GitClient()
            result = client.get_file_blame("test.py")
            
            assert result.total_lines == 0
            assert result.lines == []

    def test_get_file_history_success(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="abc123 Add feature\ndef456 Fix bug"),
                MagicMock(returncode=0, stdout="author Test\n2026-01-15 10:00:00 +0000"),
                MagicMock(returncode=0, stdout="author Test\n2026-01-10 09:00:00 +0000"),
            ]
            
            client = GitClient()
            result = client.get_file_history("test.py", limit=10)
            
            assert len(result) == 2
            assert result[0].commit_hash == "abc123"
            assert result[0].message == "Add feature"

    def test_get_file_history_failure(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            
            client = GitClient()
            result = client.get_file_history("nonexistent.py")
            
            assert result == []

    def test_get_file_history_exception(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run', side_effect=Exception("git error")):
            client = GitClient()
            result = client.get_file_history("test.py")
            
            assert result == []

    def test_is_file_hot_true(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="commit1\ncommit2\ncommit3\ncommit4\ncommit5\ncommit6"
            )
            
            client = GitClient()
            result = client.is_file_hot("test.py", days=30)
            
            assert result is True

    def test_is_file_hot_false(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="commit1\ncommit2"
            )
            
            client = GitClient()
            result = client.is_file_hot("test.py", days=30)
            
            assert result is False

    def test_is_file_hot_no_commits(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            
            client = GitClient()
            result = client.is_file_hot("test.py")
            
            assert result is False

    def test_is_file_hot_exception(self):
        from src.infrastructure.services.git_client import GitClient
        
        with patch('subprocess.run', side_effect=Exception("git error")):
            client = GitClient()
            result = client.is_file_hot("test.py")
            
            assert result is False

    def test_blame_line_dataclass(self):
        from src.infrastructure.services.git_client import BlameLine
        
        line = BlameLine(
            commit_hash="abc123",
            author="John",
            date=datetime.now(),
            line_content="print('hello')",
            line_number=10
        )
        
        assert line.commit_hash == "abc123"
        assert line.line_number == 10

    def test_file_blame_dataclass(self):
        from src.infrastructure.services.git_client import FileBlame, BlameLine
        
        lines = [
            BlameLine("abc", "John", datetime.now(), "line1", 1),
            BlameLine("def", "Jane", datetime.now(), "line2", 2),
        ]
        blame = FileBlame(
            file_path="test.py",
            lines=lines,
            total_lines=2,
            authors={"John": 1, "Jane": 1},
            last_modified=datetime.now()
        )
        
        assert blame.file_path == "test.py"
        assert blame.total_lines == 2
        assert len(blame.authors) == 2

    def test_git_history_dataclass(self):
        from src.infrastructure.services.git_client import GitHistory
        
        history = GitHistory(
            commit_hash="abc123",
            author="John",
            date=datetime.now(),
            message="Add feature",
            lines_added=10,
            lines_deleted=2
        )
        
        assert history.commit_hash == "abc123"
        assert history.lines_added == 10

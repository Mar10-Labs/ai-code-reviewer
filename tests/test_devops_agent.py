import pytest
from unittest.mock import patch, MagicMock
import subprocess

from src.agents.specialists.devops_agent import DevOpsAgent, UserChoice, Question, GitOpsResult
from src.agents.base_agent import AgentCapability


class TestDevOpsAgentInit:
    def test_agent_initialization(self):
        agent = DevOpsAgent()
        assert agent.name == "DevOps"
        assert agent.agent_type.value == "devops"

    def test_agent_capabilities(self):
        agent = DevOpsAgent()
        assert agent.can_execute(AgentCapability.EXECUTE_COMMAND)
        assert agent.can_execute(AgentCapability.FILE_SYSTEM)
        assert agent.can_execute(AgentCapability.USER_INTERACTION)


class TestDevOpsAgentVerifyState:
    @pytest.mark.asyncio
    async def test_verify_state_success(self):
        agent = DevOpsAgent()
        agent.git = MagicMock()
        agent.git.status.return_value = MagicMock(
            current_branch="main",
            is_clean=True,
            changes_to_commit=0,
            ahead=0,
            behind=0
        )
        agent.git.get_local_branches.return_value = []
        agent.git.get_orphan_branches.return_value = []
        
        result = await agent.execute({"action": "verify_state"})
                    
        assert result.success is True
        assert result.data is not None
        assert result.data.get("on_main") is True


class TestDevOpsAgentPrepareBranch:
    @pytest.mark.asyncio
    async def test_prepare_branch_creates_new_branch(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "switch_to_main", return_value=(True, "ok")):
            with patch.object(agent.git, "get_orphan_branches", return_value=[]):
                with patch.object(agent.git, "create_branch", return_value=(True, "created")):
                    result = await agent.execute({
                        "action": "prepare_branch",
                        "issue_number": 100,
                        "issue_title": "Test Issue"
                    })
        
        assert result.success is True
        assert result.data is not None
        assert "branch" in result.data

    @pytest.mark.asyncio
    async def test_prepare_branch_with_existing_branch(self):
        from src.infrastructure.services.git_service import Branch
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "switch_to_main", return_value=(True, "ok")):
            with patch.object(agent.git, "get_orphan_branches", return_value=[]):
                with patch.object(agent.git, "checkout", return_value=(True, "checked out")):
                    with patch.object(agent.git, "get_local_branches", return_value=[Branch(name="feat/100-test-issue", is_current=False)]):
                        result = await agent.execute({
                            "action": "prepare_branch",
                            "issue_number": 100,
                            "issue_title": "Test Issue"
                        })
        
        assert result.success is True


class TestDevOpsAgentCreateFile:
    @pytest.mark.asyncio
    async def test_create_file_success(self, tmp_path):
        agent = DevOpsAgent()
        
        file_path = str(tmp_path / "test.py")
        result = await agent.execute({
            "action": "create_file",
            "file_path": file_path,
            "content": "print('hello')"
        })
        
        assert result.success is True
        assert "test.py" in result.message

    @pytest.mark.asyncio
    async def test_create_file_without_path(self):
        agent = DevOpsAgent()
        
        result = await agent.execute({
            "action": "create_file",
            "content": "test"
        })
        
        assert result.success is False


class TestDevOpsAgentCommit:
    @pytest.mark.asyncio
    async def test_commit_success(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "has_uncommitted_changes", return_value=True):
            with patch.object(agent.git, "status", return_value=MagicMock(current_branch="feat/test")):
                with patch.object(agent.git, "commit", return_value=(True, "committed")):
                    result = await agent.execute({
                        "action": "commit",
                        "message": "test: commit message"
                    })
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_commit_no_changes(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "has_uncommitted_changes", return_value=False):
            result = await agent.execute({"action": "commit"})
        
        assert result.success is True
        assert "No changes" in result.message


class TestDevOpsAgentPush:
    @pytest.mark.asyncio
    async def test_push_success(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "push", return_value=(True, "pushed")):
            result = await agent.execute({"action": "push"})
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_push_failure(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "push", return_value=(False, "error")):
            result = await agent.execute({"action": "push"})
        
        assert result.success is False


class TestDevOpsAgentMerge:
    @pytest.mark.asyncio
    async def test_merge_success(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "get_conflict_files", return_value=[]):
            with patch.object(agent.git, "merge", return_value=(True, "merged")):
                result = await agent.execute({"action": "merge"})
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_merge_with_conflicts(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "get_conflict_files", return_value=["file1.py", "file2.py"]):
            result = await agent.execute({"action": "merge"})
        
        assert result.success is False
        assert "conflict" in result.message.lower()


class TestDevOpsAgentRunTests:
    @pytest.mark.asyncio
    async def test_run_tests_success(self):
        agent = DevOpsAgent()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PASSED", stderr="")
            result = await agent.execute({
                "action": "run_tests",
                "command": "pytest"
            })
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_tests_failure(self):
        agent = DevOpsAgent()
        
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="FAILED", stderr="error")
            result = await agent.execute({
                "action": "run_tests",
                "command": "pytest"
            })
        
        assert result.success is False


class TestDevOpsAgentGenerateBranchName:
    def test_generate_branch_name_with_title(self):
        agent = DevOpsAgent()
        name = agent._generate_branch_name(1, "Add new feature")
        assert "feat" in name
        assert "1" in name

    def test_generate_branch_name_without_title(self):
        agent = DevOpsAgent()
        name = agent._generate_branch_name(2, "")
        assert "feat" in name
        assert "2" in name

    def test_generate_branch_name_special_chars(self):
        agent = DevOpsAgent()
        name = agent._generate_branch_name(3, "Test @#$% Feature!")
        assert "#" not in name
        assert "@" not in name


class TestDevOpsAgentGenerateStatusReport:
    def test_status_report_format(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "status") as mock_status:
            mock_status.return_value = MagicMock(
                current_branch="main",
                is_clean=True,
                ahead=0,
                behind=0
            )
            with patch.object(agent.git, "get_local_branches", return_value=[]):
                report = agent.generate_status_report()
                
        assert "main" in report
        assert "YES" in report or "✓" in report


class TestDevOpsAgentUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        agent = DevOpsAgent()
        result = await agent.execute({"action": "unknown_action"})
        
        assert result.success is False
        assert "Unknown action" in result.message


class TestDevOpsAgentHelperMethods:
    def test_classify_branch_type(self):
        agent = DevOpsAgent()
        
        assert agent.git.classify_branch_type("feat/new-feature").value == "feat"
        assert agent.git.classify_branch_type("fix/bug-fix").value == "fix"
        assert agent.git.classify_branch_type("chore/update-deps").value == "chore"
        assert agent.git.classify_branch_type("refactor/code").value == "refactor"
        assert agent.git.classify_branch_type("docs/readme").value == "docs"

    def test_extract_issue_number(self):
        agent = DevOpsAgent()
        
        assert agent.git.extract_issue_number("feat/123-title") == 123
        assert agent.git.extract_issue_number("fix/#456-bug") == 456
        assert agent.git.extract_issue_number("no-number") is None


class TestDevOpsAgentPrepareBranchEdge:
    @pytest.mark.asyncio
    async def test_prepare_branch_switch_to_main_fails(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "switch_to_main", return_value=(False, "error")):
            result = await agent.execute({
                "action": "prepare_branch",
                "issue_number": 100,
                "issue_title": "Test Issue"
            })
        
        assert result.success is False
        assert "main" in result.message.lower()

    @pytest.mark.asyncio
    async def test_prepare_branch_with_auto_mode(self):
        from src.infrastructure.services.git_service import Branch
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "switch_to_main", return_value=(True, "ok")):
            with patch.object(agent.git, "get_orphan_branches", return_value=[
                Branch(name="feat/50-old-feature", is_current=False),
                Branch(name="feat/60-old-feature", is_current=False),
            ]):
                with patch.object(agent.git, "create_branch", return_value=(True, "created")):
                    result = await agent.execute({
                        "action": "prepare_branch",
                        "issue_number": 100,
                        "issue_title": "Test Issue",
                        "auto_mode": True
                    })
        
        assert result.success is True


class TestDevOpsAgentFullWorkflow:
    @pytest.mark.asyncio
    async def test_full_workflow_success(self, tmp_path):
        agent = DevOpsAgent()
        
        test_file = str(tmp_path / "test_workflow.py")
        
        with patch.object(agent.git, "status") as mock_status:
            mock_status.return_value = MagicMock(
                current_branch="main",
                is_clean=True,
                changes_to_commit=0,
                ahead=0,
                behind=0
            )
            with patch.object(agent.git, "get_local_branches", return_value=[]):
                with patch.object(agent.git, "get_orphan_branches", return_value=[]):
                    with patch.object(agent.git, "switch_to_main", return_value=(True, "ok")):
                        with patch.object(agent.git, "create_branch", return_value=(True, "created")):
                            with patch.object(agent.git, "has_uncommitted_changes", return_value=False):
                                with patch("subprocess.run") as mock_run:
                                    mock_run.return_value = MagicMock(returncode=0, stdout="PASSED", stderr="")
                                    result = await agent._full_workflow({
                                        "issue_number": 99,
                                        "issue_title": "Test workflow",
                                        "files": [{"file_path": test_file, "content": "# test"}],
                                        "test_command": "pytest"
                                    })
        
        assert result.data is not None
        assert "steps" in result.data

    @pytest.mark.asyncio
    async def test_full_workflow_branch_failure(self):
        agent = DevOpsAgent()
        
        with patch.object(agent.git, "status") as mock_status:
            mock_status.return_value = MagicMock(
                current_branch="main",
                is_clean=True,
                changes_to_commit=0,
                ahead=0,
                behind=0
            )
            with patch.object(agent.git, "get_local_branches", return_value=[]):
                with patch.object(agent.git, "get_orphan_branches", return_value=[]):
                    with patch.object(agent.git, "switch_to_main", return_value=(True, "ok")):
                        with patch.object(agent.git, "create_branch", return_value=(False, "failed")):
                            result = await agent._full_workflow({
                                "issue_number": 98,
                                "issue_title": "Test workflow",
                                "files": [],
                            })
        
        assert result.success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

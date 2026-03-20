import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.agents.master_agent import MasterAgent, Intent, ConversationContext, MasterResponse


class TestMasterAgentInit:
    def test_agent_initialization(self):
        agent = MasterAgent()
        assert agent.devops is not None
        assert agent.context is not None

    def test_available_commands(self):
        agent = MasterAgent()
        commands = agent.get_available_commands()
        assert len(commands) > 0
        assert any("execute" in c.lower() for c in commands)


class TestMasterAgentClassifyIntent:
    def test_execute_issue_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("execute #10") == Intent.EXECUTE_ISSUE
        assert agent.classify_intent("execute #123") == Intent.EXECUTE_ISSUE
        assert agent.classify_intent("issue #5") == Intent.EXECUTE_ISSUE

    def test_status_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("status") == Intent.CHECK_STATUS
        assert agent.classify_intent("git status") == Intent.CHECK_STATUS
        assert agent.classify_intent("estado") == Intent.CHECK_STATUS

    def test_branch_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("create branch") == Intent.CREATE_BRANCH
        assert agent.classify_intent("new branch #15") == Intent.CREATE_BRANCH

    def test_commit_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("commit") == Intent.COMMIT_CHANGES
        assert agent.classify_intent("commits") == Intent.COMMIT_CHANGES

    def test_merge_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("merge") == Intent.MERGE_BRANCH
        assert agent.classify_intent("pr") == Intent.MERGE_BRANCH
        assert agent.classify_intent("pull request") == Intent.MERGE_BRANCH

    def test_test_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("test") == Intent.RUN_TESTS
        assert agent.classify_intent("pytest") == Intent.RUN_TESTS
        assert agent.classify_intent("tests") == Intent.RUN_TESTS

    def test_help_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("help") == Intent.HELP
        assert agent.classify_intent("ayuda") == Intent.HELP
        assert agent.classify_intent("comandos") == Intent.HELP

    def test_unknown_intent(self):
        agent = MasterAgent()
        
        assert agent.classify_intent("random text") == Intent.UNKNOWN
        assert agent.classify_intent("something else") == Intent.UNKNOWN


class TestMasterAgentExtractIssue:
    def test_extract_issue_number_hash(self):
        agent = MasterAgent()
        
        assert agent.extract_issue_number("#10") == 10
        assert agent.extract_issue_number("#123") == 123

    def test_extract_issue_number_no_hash(self):
        agent = MasterAgent()
        
        assert agent.extract_issue_number("execute #5") == 5
        assert agent.extract_issue_number("issue #42") == 42

    def test_extract_issue_number_not_found(self):
        agent = MasterAgent()
        
        assert agent.extract_issue_number("no issue") is None


class TestMasterAgentGuessTitle:
    def test_known_issue_titles(self):
        agent = MasterAgent()
        
        assert "AgentState" in agent._guess_issue_title("", 10)
        assert "ReviewComment" in agent._guess_issue_title("", 11)
        assert "MCP" in agent._guess_issue_title("", 12)

    def test_unknown_issue_title(self):
        agent = MasterAgent()
        
        title = agent._guess_issue_title("", 999)
        assert "999" in title


class TestMasterAgentHandleHelp:
    @pytest.mark.asyncio
    async def test_help_returns_commands(self):
        agent = MasterAgent()
        response = await agent._handle_help("help")
        
        assert response.intent == Intent.HELP
        assert "COMMANDS" in response.message or "comando" in response.message.lower()


class TestMasterAgentHandleCheckStatus:
    @pytest.mark.asyncio
    async def test_check_status_returns_report(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"current_branch": "main"}
            )
            with patch.object(agent.devops, "generate_status_report", return_value="Git status report"):
                response = await agent._handle_check_status("status")
                
        assert response.intent == Intent.CHECK_STATUS
        assert "Git" in response.message or "git" in response.message.lower()


class TestMasterAgentHandleCreateBranch:
    @pytest.mark.asyncio
    async def test_create_branch_success(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"branch": "feat/100-test"},
                message="Branch created"
            )
            response = await agent._handle_create_branch("create branch #100")
            
        assert response.intent == Intent.CREATE_BRANCH
        assert "100" in response.message or "test" in response.message.lower()

    @pytest.mark.asyncio
    async def test_create_branch_no_issue(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={"branch": "feat/0-new-feature"},
                message="Branch created"
            )
            response = await agent._handle_create_branch("create branch")
            
        assert response.intent == Intent.CREATE_BRANCH


class TestMasterAgentHandleCommit:
    @pytest.mark.asyncio
    async def test_commit_success(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                message="Commit successful"
            )
            response = await agent._handle_commit("commit")
            
        assert response.intent == Intent.COMMIT_CHANGES
        assert len(response.questions) == 1

    @pytest.mark.asyncio
    async def test_commit_failure(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=False,
                message="Commit failed"
            )
            response = await agent._handle_commit("commit")
            
        assert response.intent == Intent.COMMIT_CHANGES
        assert len(response.questions) == 0


class TestMasterAgentHandleMerge:
    @pytest.mark.asyncio
    async def test_merge_success(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                message="Merge successful"
            )
            response = await agent._handle_merge("merge")
            
        assert response.intent == Intent.MERGE_BRANCH
        assert agent.context.workflow_step == "completed"
        assert len(response.questions) == 1

    @pytest.mark.asyncio
    async def test_merge_failure(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=False,
                message="Merge failed"
            )
            response = await agent._handle_merge("merge")
            
        assert response.intent == Intent.MERGE_BRANCH
        assert len(response.questions) == 0


class TestMasterAgentExecuteIssue:
    @pytest.mark.asyncio
    async def test_execute_issue_no_issue_number(self):
        agent = MasterAgent()
        response = await agent._handle_execute_issue("execute issue")
        
        assert response.intent == Intent.EXECUTE_ISSUE
        assert len(response.questions) == 1

    @pytest.mark.asyncio
    async def test_execute_issue_with_actions_needed(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=True,
                data={
                    "on_main": False,
                    "current_branch": "feat/10-old",
                    "orphan_branches": ["feat/10-old"],
                    "is_clean": False,
                    "changes_count": 3
                }
            )
            response = await agent._handle_execute_issue("execute #10")
            
        assert response.intent == Intent.EXECUTE_ISSUE
        assert len(response.questions) == 1
        assert "prepare_issue" in response.questions[0]["id"]

    @pytest.mark.asyncio
    async def test_prepare_and_execute_branch_failure(self):
        agent = MasterAgent()
        agent.context.current_issue_title = "Test"
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(
                success=False,
                message="Failed to create branch"
            )
            response = await agent._prepare_and_execute(10)
            
        assert response.intent == Intent.EXECUTE_ISSUE
        assert "error" in response.message.lower() or "failed" in response.message.lower()


class TestMasterAgentHandleRunTests:
    @pytest.mark.asyncio
    async def test_run_tests_success(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(success=True, message="Tests passed")
            response = await agent._handle_run_tests("pytest")
            
        assert response.intent == Intent.RUN_TESTS

    @pytest.mark.asyncio
    async def test_run_tests_failure(self):
        agent = MasterAgent()
        
        with patch.object(agent.devops, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = MagicMock(success=False, message="Tests failed")
            response = await agent._handle_run_tests("pytest")
            
        assert response.intent == Intent.RUN_TESTS


class TestMasterAgentHandleUnknown:
    @pytest.mark.asyncio
    async def test_unknown_returns_error_message(self):
        agent = MasterAgent()
        response = await agent._handle_unknown("random unknown command")
        
        assert response.intent == Intent.UNKNOWN
        assert "help" in response.message.lower() or "comando" in response.message.lower()


class TestMasterAgentProcess:
    @pytest.mark.asyncio
    async def test_process_status(self):
        agent = MasterAgent()
        
        with patch.object(agent, "_handle_check_status", new_callable=AsyncMock) as mock_handler:
            mock_handler.return_value = MasterResponse(
                intent=Intent.CHECK_STATUS,
                message="Status report"
            )
            response = await agent.process("status")
            
        assert response.intent == Intent.CHECK_STATUS

    @pytest.mark.asyncio
    async def test_process_help(self):
        agent = MasterAgent()
        
        with patch.object(agent, "_handle_help", new_callable=AsyncMock) as mock_handler:
            mock_handler.return_value = MasterResponse(
                intent=Intent.HELP,
                message="Help text"
            )
            response = await agent.process("help")
            
        assert response.intent == Intent.HELP


class TestConversationContext:
    def test_context_default_values(self):
        ctx = ConversationContext()
        
        assert ctx.current_issue is None
        assert ctx.current_issue_title == ""
        assert ctx.workflow_step == "idle"
        assert ctx.auto_mode is False


class TestMasterResponse:
    def test_response_creation(self):
        response = MasterResponse(
            intent=Intent.CHECK_STATUS,
            message="Test message"
        )
        
        assert response.intent == Intent.CHECK_STATUS
        assert response.message == "Test message"
        assert response.agent_results == []
        assert response.questions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

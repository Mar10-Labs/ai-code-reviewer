import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.agents.master_agent import MasterAgent, Intent, ConversationContext, MasterResponse


class TestMasterAgentInit:
    def test_agent_initialization(self):
        agent = MasterAgent()
        assert agent.graph is not None
        assert agent.context is not None

    def test_available_commands(self):
        agent = MasterAgent()
        commands = agent.get_available_commands()
        assert len(commands) > 0
        assert any("review" in c.lower() for c in commands)


class TestMasterAgentClassifyIntent:
    def test_review_intent(self):
        agent = MasterAgent()
        assert agent.classify_intent("review pr") == Intent.REVIEW_PR
        assert agent.classify_intent("review #10") == Intent.REVIEW_PR

    def test_analyze_intent(self):
        agent = MasterAgent()
        assert agent.classify_intent("analyze file.py") == Intent.ANALYZE_FILE
        assert agent.classify_intent("check code") == Intent.ANALYZE_FILE

    def test_help_intent(self):
        agent = MasterAgent()
        assert agent.classify_intent("help") == Intent.HELP
        assert agent.classify_intent("ayuda") == Intent.HELP

    def test_unknown_intent(self):
        agent = MasterAgent()
        assert agent.classify_intent("random text") == Intent.UNKNOWN


class TestMasterAgentReviewPR:
    @pytest.mark.asyncio
    async def test_review_pr_returns_response(self):
        agent = MasterAgent()
        
        diff = "def hello():\n    password = 'secret'\n    return True"
        
        response = await agent.review_pr(diff, "test/repo", 1)
        
        assert response.intent == Intent.REVIEW_PR
        assert response.message is not None
        assert "issues" in response.message.lower()

    @pytest.mark.asyncio
    async def test_review_pr_updates_context(self):
        agent = MasterAgent()
        
        diff = "def hello(): pass"
        
        response = await agent.review_pr(diff, "test/repo", 42)
        
        assert agent.context.repository == "test/repo"
        assert agent.context.pr_number == 42
        assert agent.context.diff_content == diff

    @pytest.mark.asyncio
    async def test_review_pr_detects_issues(self):
        agent = MasterAgent()
        
        diff = "password = 'hardcoded_secret'"
        
        response = await agent.review_pr(diff, "test/repo", 1)
        
        assert response.summary is not None
        assert "total_issues" in response.summary


class TestMasterAgentProcess:
    @pytest.mark.asyncio
    async def test_process_review_command(self):
        agent = MasterAgent()
        
        with patch.object(agent, "review_pr", new_callable=AsyncMock) as mock_review:
            mock_review.return_value = MasterResponse(
                intent=Intent.REVIEW_PR,
                message="Review completed"
            )
            response = await agent.process("review pr")
        
        assert response.intent == Intent.REVIEW_PR

    @pytest.mark.asyncio
    async def test_process_help_command(self):
        agent = MasterAgent()
        response = await agent.process("help")
        assert response.intent == Intent.HELP
        assert "CODE REVIEWER" in response.message

    @pytest.mark.asyncio
    async def test_process_unknown_command(self):
        agent = MasterAgent()
        response = await agent.process("random unknown command")
        assert response.intent == Intent.UNKNOWN
        assert "help" in response.message.lower()


class TestConversationContext:
    def test_context_default_values(self):
        ctx = ConversationContext()
        assert ctx.repository == ""
        assert ctx.pr_number is None
        assert ctx.diff_content == ""
        assert ctx.workflow_step == "idle"


class TestMasterResponse:
    def test_response_creation(self):
        response = MasterResponse(
            intent=Intent.REVIEW_PR,
            message="Test message"
        )
        assert response.intent == Intent.REVIEW_PR
        assert response.message == "Test message"
        assert response.agent_results == []
        assert response.summary == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

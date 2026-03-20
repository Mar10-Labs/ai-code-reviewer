import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.agents.master_agent import MasterAgent, Intent, ConversationContext, MasterResponse


class TestMasterAgentInit:
    def test_agent_initialization(self):
        agent = MasterAgent()
        assert agent.agents is not None
        assert len(agent.agents) == 5
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
    async def test_review_pr_runs_all_agents(self):
        agent = MasterAgent()
        
        diff = "def hello():\n    password = 'secret'\n    return True"
        
        with patch.object(agent.agents[0], "execute", new_callable=AsyncMock) as mock_cq:
            with patch.object(agent.agents[1], "execute", new_callable=AsyncMock) as mock_perf:
                with patch.object(agent.agents[2], "execute", new_callable=AsyncMock) as mock_sec:
                    with patch.object(agent.agents[3], "execute", new_callable=AsyncMock) as mock_doc:
                        with patch.object(agent.agents[4], "execute", new_callable=AsyncMock) as mock_test:
                            mock_cq.return_value = {"agent": "CodeQuality", "results": [], "summary": "0 issues"}
                            mock_perf.return_value = {"agent": "Performance", "results": [], "summary": "0 issues"}
                            mock_sec.return_value = {"agent": "Security", "results": [], "summary": "0 issues"}
                            mock_doc.return_value = {"agent": "Documentation", "results": [], "summary": "0 issues"}
                            mock_test.return_value = {"agent": "Testing", "results": [], "summary": "0 issues"}
                            
                            response = await agent.review_pr(diff, "test/repo", 1)
        
        assert response.intent == Intent.REVIEW_PR
        assert len(response.agent_results) == 5

    @pytest.mark.asyncio
    async def test_review_pr_detects_security_issues(self):
        agent = MasterAgent()
        
        diff = "password = 'hardcoded_secret'"
        
        with patch.object(agent.agents[2], "execute", new_callable=AsyncMock) as mock_sec:
            from src.agents.specialists.security_agent import ReviewResult
            mock_sec.return_value = {
                "agent": "Security",
                "results": [
                    ReviewResult(
                        file_path="test.py",
                        line_number=1,
                        severity="critical",
                        category="security",
                        comment="Hardcoded secret detected",
                        suggested_fix="Use environment variable"
                    )
                ],
                "summary": "1 security issue"
            }
            
            response = await agent.review_pr(diff, "test/repo", 1)
        
        assert response.summary["total_issues"] >= 1
        assert response.summary["critical"] >= 1


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

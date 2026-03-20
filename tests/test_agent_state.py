import pytest
from src.models.agent_state import AgentState, ReviewComment, EnrichedDiff


class TestAgentState:
    def test_agent_state_creation(self):
        state = AgentState(
            pr_id=123,
            pr_title="Test PR",
            repository="test/repo"
        )
        assert state.pr_id == 123
        assert state.status == "pending"
        assert len(state.review_comments) == 0

    def test_agent_state_with_comments(self):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=10,
            severity="warning",
            category="quality",
            comment="This function is too long, consider splitting it.",
            confidence=0.85
        )
        state = AgentState(
            pr_id=123,
            pr_title="Test PR",
            repository="test/repo",
            review_comments=[comment]
        )
        assert len(state.review_comments) == 1
        assert state.review_comments[0].severity == "warning"

    def test_review_comment_validation(self):
        with pytest.raises(Exception):
            ReviewComment(
                file_path="test.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="Too short",  # min_length=20
                confidence=0.5
            )


class TestEnrichedDiff:
    def test_enriched_diff_creation(self):
        diff = EnrichedDiff(
            file_path="src/main.py",
            language="python",
            diff_content="+def new_func():\n    pass",
            num_additions=2,
            num_deletions=0
        )
        assert diff.language == "python"
        assert diff.num_additions == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

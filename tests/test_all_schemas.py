import pytest
from pydantic import ValidationError
from datetime import datetime, timezone

from src.models.agent_state import AgentState, EnrichedDiff, ReviewComment
from src.models.review_comment import (
    ReviewComment as RC,
    ReviewCommentCollection,
    SeveritySummary,
    summarize_by_severity
)


class TestAgentStateSchema:
    def test_agent_state_required_fields(self):
        state = AgentState(
            pr_id=1,
            pr_title="Test PR",
            repository="owner/repo"
        )
        assert state.pr_id == 1
        assert state.status == "pending"
        assert len(state.enriched_diffs) == 0
        assert len(state.review_comments) == 0

    def test_agent_state_all_statuses(self):
        for status in ["pending", "processing", "completed", "failed"]:
            state = AgentState(
                pr_id=1,
                pr_title="Test",
                repository="repo",
                status=status
            )
            assert state.status == status

    def test_agent_state_with_diffs(self):
        diff = EnrichedDiff(
            file_path="src/main.py",
            language="python",
            diff_content="+def new(): pass",
            num_additions=1,
            num_deletions=0
        )
        state = AgentState(
            pr_id=1,
            pr_title="Test",
            repository="repo",
            enriched_diffs=[diff]
        )
        assert len(state.enriched_diffs) == 1
        assert state.enriched_diffs[0].language == "python"

    def test_agent_state_with_comments(self):
        comment = RC(
            file_path="src/main.py",
            line_number=10,
            severity="warning",
            category="quality",
            comment="This is a valid comment with enough words here.",
            confidence=0.8
        )
        state = AgentState(
            pr_id=1,
            pr_title="Test",
            repository="repo",
            review_comments=[comment]
        )
        assert len(state.review_comments) == 1
        assert state.review_comments[0].severity == "warning"

    def test_agent_state_timestamps(self):
        state = AgentState(
            pr_id=1,
            pr_title="Test",
            repository="repo"
        )
        assert state.created_at is not None
        assert state.updated_at is not None
        assert isinstance(state.created_at, datetime)

    def test_agent_state_agent_name(self):
        state = AgentState(
            pr_id=1,
            pr_title="Test",
            repository="repo",
            agent_name="SecurityAgent"
        )
        assert state.agent_name == "SecurityAgent"


class TestEnrichedDiffSchema:
    def test_enriched_diff_required(self):
        diff = EnrichedDiff(
            file_path="test.py",
            language="python",
            diff_content="+code",
            num_additions=1,
            num_deletions=0
        )
        assert diff.file_path == "test.py"
        assert diff.num_additions == 1

    def test_enriched_diff_chunks(self):
        diff = EnrichedDiff(
            file_path="test.py",
            language="python",
            diff_content="+chunk1\n+chunk2",
            num_additions=2,
            num_deletions=0,
            chunks=["chunk1", "chunk2"]
        )
        assert len(diff.chunks) == 2

    def test_enriched_diff_multiple_languages(self):
        for lang in ["python", "javascript", "java", "go", "rust"]:
            diff = EnrichedDiff(
                file_path=f"main.{lang}",
                language=lang,
                diff_content="+code",
                num_additions=1,
                num_deletions=0
            )
            assert diff.language == lang


class TestReviewCommentSchema:
    def test_review_comment_required(self):
        comment = RC(
            file_path="src/main.py",
            line_number=1,
            severity="warning",
            category="quality",
            comment="This is a valid comment with enough words to pass validation.",
            confidence=0.5
        )
        assert comment.severity == "warning"
        assert comment.category == "quality"

    def test_review_comment_all_severities(self):
        for severity in ["critical", "warning", "suggestion"]:
            comment = RC(
                file_path="test.py",
                line_number=1,
                severity=severity,
                category="quality",
                comment="This comment is valid with sufficient words.",
                confidence=0.5
            )
            assert comment.severity == severity

    def test_review_comment_all_categories(self):
        categories = [
            "security", "performance", "quality", "debt",
            "tests", "architecture", "style", "docs"
        ]
        for cat in categories:
            comment = RC(
                file_path="test.py",
                line_number=1,
                severity="warning",
                category=cat,
                comment="This comment is valid with enough words to pass.",
                confidence=0.5
            )
            assert comment.category == cat

    def test_review_comment_confidence_boundaries(self):
        comment_low = RC(
            file_path="test.py",
            line_number=1,
            severity="suggestion",
            category="style",
            comment="Low confidence comment with sufficient words here.",
            confidence=0.0
        )
        assert comment_low.confidence == 0.0

        comment_high = RC(
            file_path="test.py",
            line_number=1,
            severity="critical",
            category="security",
            comment="High confidence comment with sufficient words here.",
            confidence=1.0
        )
        assert comment_high.confidence == 1.0

    def test_review_comment_invalid_confidence(self):
        with pytest.raises(ValidationError):
            RC(
                file_path="test.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="This comment is valid and should trigger the error.",
                confidence=1.5
            )

    def test_review_comment_suggested_fix_optional(self):
        comment = RC(
            file_path="test.py",
            line_number=1,
            severity="warning",
            category="quality",
            comment="Comment without suggested fix with enough words here.",
            confidence=0.5
        )
        assert comment.suggested_fix is None


class TestReviewCommentCollectionSchema:
    def test_collection_empty(self):
        collection = ReviewCommentCollection()
        assert len(collection.comments) == 0
        assert collection.total_count == 0

    def test_collection_with_multiple_comments(self):
        comments = [
            RC(
                file_path="a.py",
                line_number=1,
                severity="critical",
                category="security",
                comment="Critical security issue with enough words here.",
                confidence=0.9
            ),
            RC(
                file_path="b.py",
                line_number=5,
                severity="warning",
                category="performance",
                comment="Performance warning with enough words here.",
                confidence=0.7
            ),
            RC(
                file_path="c.py",
                line_number=10,
                severity="suggestion",
                category="style",
                comment="Style suggestion with enough words here.",
                confidence=0.5
            ),
        ]
        collection = ReviewCommentCollection(
            comments=comments,
            total_count=3
        )
        assert len(collection.comments) == 3
        assert collection.total_count == 3


class TestSeveritySummarySchema:
    def test_summary_empty(self):
        summary = SeveritySummary()
        assert summary.critical == 0
        assert summary.warning == 0
        assert summary.suggestion == 0
        assert summary.total == 0

    def test_summary_with_counts(self):
        summary = SeveritySummary(
            critical=5,
            warning=10,
            suggestion=15
        )
        assert summary.total == 30
        assert summary.to_dict() == {
            "critical": 5,
            "warning": 10,
            "suggestion": 15,
            "total": 30
        }

    def test_summarize_by_severity_empty(self):
        summary = summarize_by_severity([])
        assert summary.total == 0

    def test_summarize_by_severity_mixed(self):
        comments = [
            RC(file_path="a.py", line_number=1, severity="critical", category="security", comment="Critical one with enough words.", confidence=0.9),
            RC(file_path="b.py", line_number=1, severity="critical", category="security", comment="Critical two with enough words.", confidence=0.9),
            RC(file_path="c.py", line_number=1, severity="warning", category="quality", comment="Warning one with enough words.", confidence=0.7),
            RC(file_path="d.py", line_number=1, severity="suggestion", category="style", comment="Suggestion one with enough words.", confidence=0.5),
            RC(file_path="e.py", line_number=1, severity="suggestion", category="style", comment="Suggestion two with enough words.", confidence=0.5),
        ]
        summary = summarize_by_severity(comments)
        assert summary.critical == 2
        assert summary.warning == 1
        assert summary.suggestion == 2
        assert summary.total == 5


class TestEdgeCases:
    def test_very_long_file_path(self):
        long_path = "src/" + "a/" * 100 + "file.py"
        comment = RC(
            file_path=long_path,
            line_number=1,
            severity="warning",
            category="quality",
            comment="Very long path comment with enough words here.",
            confidence=0.5
        )
        assert len(comment.file_path) > 100

    def test_very_long_comment_rejected(self):
        long_comment = "Word " * 101
        with pytest.raises(ValidationError):
            RC(
                file_path="test.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment=long_comment,
                confidence=0.5
            )

    def test_special_characters_in_path(self):
        comment = RC(
            file_path="src/api/v1/routes/users.py",
            line_number=42,
            severity="warning",
            category="quality",
            comment="Path with special chars and numbers 12345 here.",
            confidence=0.5
        )
        assert "/" in comment.file_path

    def test_max_confidence_exactly(self):
        comment = RC(
            file_path="test.py",
            line_number=1,
            severity="critical",
            category="security",
            comment="Max confidence comment with enough words here.",
            confidence=0.999999
        )
        assert comment.confidence <= 1.0

    def test_min_confidence_exactly(self):
        comment = RC(
            file_path="test.py",
            line_number=1,
            severity="suggestion",
            category="style",
            comment="Min confidence comment with enough words here.",
            confidence=0.000001
        )
        assert comment.confidence >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

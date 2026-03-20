import pytest
from pydantic import ValidationError
from src.models.review_comment import (
    ReviewComment,
    ReviewCommentCollection,
    SeveritySummary,
    summarize_by_severity
)


class TestReviewCommentValidation:
    def test_valid_comment(self):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=42,
            severity="warning",
            category="security",
            comment="This function does not validate input parameters, which could lead to injection attacks.",
            confidence=0.85
        )
        assert comment.file_path == "src/main.py"
        assert comment.line_number == 42
        assert comment.severity == "warning"
        assert comment.category == "security"
        assert comment.confidence == 0.85

    def test_comment_with_suggested_fix(self):
        comment = ReviewComment(
            file_path="tests/test_main.py",
            line_number=100,
            severity="suggestion",
            category="style",
            comment="Consider using snake_case for variable naming in Python code.",
            suggested_fix="Rename 'myVariable' to 'my_variable'",
            confidence=0.95
        )
        assert comment.suggested_fix is not None
        assert "my_variable" in comment.suggested_fix

    def test_file_path_min_length(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="",
                line_number=1,
                severity="warning",
                category="quality",
                comment="This comment is long enough to be valid and complete.",
                confidence=0.8
            )
        assert "file_path" in str(exc_info.value)

    def test_file_path_with_whitespace(self):
        comment = ReviewComment(
            file_path=" src/main.py",
            line_number=1,
            severity="warning",
            category="quality",
            comment="This comment is valid and should be stripped of whitespace.",
            confidence=0.8
        )
        assert comment.file_path == "src/main.py"

    def test_file_path_with_parent_directory(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="../etc/passwd",
                line_number=1,
                severity="critical",
                category="security",
                comment="Path traversal attempt detected in the codebase review.",
                confidence=0.99
            )
        assert ".." in str(exc_info.value)

    def test_line_number_must_be_positive(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="src/main.py",
                line_number=0,
                severity="warning",
                category="quality",
                comment="This comment is valid and should trigger the error.",
                confidence=0.8
            )
        assert "line_number" in str(exc_info.value)

    def test_line_number_negative(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="src/main.py",
                line_number=-5,
                severity="warning",
                category="quality",
                comment="This comment is valid and should trigger the error.",
                confidence=0.8
            )
        assert "line_number" in str(exc_info.value)

    def test_comment_min_length(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="Too short",
                confidence=0.8
            )
        assert "comment" in str(exc_info.value)

    def test_comment_min_words(self):
        with pytest.raises(ValidationError) as exc_info:
            ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="Short.",
                confidence=0.8
            )
        assert "string_too_short" in str(exc_info.value) or "comment" in str(exc_info.value).lower()

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="This comment is valid and long enough to pass validation checks.",
                confidence=1.5
            )

    def test_confidence_negative(self):
        with pytest.raises(ValidationError):
            ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity="warning",
                category="quality",
                comment="This comment is valid and long enough to pass validation checks.",
                confidence=-0.1
            )

    def test_confidence_zero_valid(self):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=1,
            severity="suggestion",
            category="style",
            comment="This comment has minimum confidence and should pass validation here.",
            confidence=0.0
        )
        assert comment.confidence == 0.0

    def test_confidence_one_valid(self):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=1,
            severity="critical",
            category="security",
            comment="This comment has maximum confidence and should pass validation now.",
            confidence=1.0
        )
        assert comment.confidence == 1.0

    def test_all_severity_levels(self):
        for severity in ["critical", "warning", "suggestion"]:
            comment = ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity=severity,
                category="quality",
                comment="This comment validates that all severity levels work correctly.",
                confidence=0.8
            )
            assert comment.severity == severity

    def test_all_categories(self):
        categories = [
            "security", "performance", "quality", "debt", 
            "tests", "architecture", "style", "docs"
        ]
        for category in categories:
            comment = ReviewComment(
                file_path="src/main.py",
                line_number=1,
                severity="warning",
                category=category,
                comment="This comment validates that all category types work correctly.",
                confidence=0.8
            )
            assert comment.category == category


class TestReviewCommentCollection:
    def test_empty_collection(self):
        collection = ReviewCommentCollection()
        assert len(collection.comments) == 0
        assert collection.total_count == 0

    def test_collection_with_comments(self):
        comments = [
            ReviewComment(
                file_path="src/a.py",
                line_number=1,
                severity="critical",
                category="security",
                comment="This is the first comment with enough words to pass.",
                confidence=0.9
            ),
            ReviewComment(
                file_path="src/b.py",
                line_number=5,
                severity="warning",
                category="quality",
                comment="This is the second comment with enough words to pass.",
                confidence=0.8
            )
        ]
        collection = ReviewCommentCollection(
            comments=comments,
            total_count=2
        )
        assert len(collection.comments) == 2
        assert collection.total_count == 2


class TestSeveritySummary:
    def test_empty_summary(self):
        summary = SeveritySummary()
        assert summary.critical == 0
        assert summary.warning == 0
        assert summary.suggestion == 0
        assert summary.total == 0

    def test_summary_properties(self):
        summary = SeveritySummary(critical=2, warning=3, suggestion=5)
        assert summary.total == 10

    def test_summarize_by_severity(self):
        comments = [
            ReviewComment(
                file_path="a.py", line_number=1, severity="critical",
                category="security", comment="First critical comment with enough words here.",
                confidence=0.9
            ),
            ReviewComment(
                file_path="b.py", line_number=2, severity="critical",
                category="security", comment="Second critical comment with enough words here.",
                confidence=0.8
            ),
            ReviewComment(
                file_path="c.py", line_number=3, severity="warning",
                category="quality", comment="First warning comment with enough words here.",
                confidence=0.7
            ),
            ReviewComment(
                file_path="d.py", line_number=4, severity="suggestion",
                category="style", comment="First suggestion comment with enough words here.",
                confidence=0.6
            ),
        ]
        summary = summarize_by_severity(comments)
        assert summary.critical == 2
        assert summary.warning == 1
        assert summary.suggestion == 1
        assert summary.total == 4

    def test_to_dict(self):
        summary = SeveritySummary(critical=1, warning=2, suggestion=3)
        result = summary.to_dict()
        assert result == {"critical": 1, "warning": 2, "suggestion": 3, "total": 6}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest
from unittest.mock import MagicMock

from src.infrastructure.services.github_actions import (
    GitHubActionsExecutor,
    CheckConclusion,
    ActionResult,
    execute_review_actions,
)
from src.infrastructure.services.pr_scorer import PRScoring, ScoringFactor
from src.infrastructure.services.comment_publisher import Finding, Severity


class TestCheckConclusion:
    def test_success_conclusion(self):
        assert CheckConclusion.SUCCESS.value == "success"

    def test_failure_conclusion(self):
        assert CheckConclusion.FAILURE.value == "failure"

    def test_action_required_conclusion(self):
        assert CheckConclusion.ACTION_REQUIRED.value == "action_required"


class TestGitHubActionsExecutor:
    def test_creates_failure_check_for_blocking_pr(self):
        executor = GitHubActionsExecutor(
            repo_owner="owner",
            repo_name="repo",
            pr_number=123,
        )
        
        scoring = PRScoring(
            risk_score=0.85,
            complexity="high",
            requires_human_review=True,
            blocking=True,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=["Blocking issue"],
            summary="High risk PR"
        )
        
        check = executor._create_check_run(scoring, [], [])
        
        assert check.conclusion == CheckConclusion.FAILURE
        assert "Blocking" in check.title

    def test_creates_warning_check_for_warnings(self):
        executor = GitHubActionsExecutor("owner", "repo", 123)
        
        scoring = PRScoring(
            risk_score=0.4,
            complexity="medium",
            requires_human_review=False,
            blocking=False,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=["Minor warning"],
            summary="Low risk PR"
        )
        
        warning_finding = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.WARNING,
            category="style",
            comment="Warning",
            confidence=0.9,
        )
        
        check = executor._create_check_run(scoring, [], [warning_finding])
        
        assert check.conclusion == CheckConclusion.WARNING

    def test_creates_success_check_for_clean_pr(self):
        executor = GitHubActionsExecutor("owner", "repo", 123)
        
        scoring = PRScoring(
            risk_score=0.1,
            complexity="low",
            requires_human_review=False,
            blocking=False,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=["All good"],
            summary="Low risk PR"
        )
        
        check = executor._create_check_run(scoring, [], [])
        
        assert check.conclusion == CheckConclusion.SUCCESS
        assert "Passed" in check.title

    def test_adds_high_risk_label_for_blocking_pr(self):
        executor = GitHubActionsExecutor("owner", "repo", 123)
        
        scoring = PRScoring(
            risk_score=0.85,
            complexity="high",
            requires_human_review=True,
            blocking=True,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=[],
            summary=""
        )
        
        labels = executor._add_risk_labels(scoring)
        
        assert "high-risk" in labels

    def test_creates_tech_debt_issue(self):
        executor = GitHubActionsExecutor("owner", "repo", 123)
        
        tech_debt = [
            Finding(
                file_path="test.py",
                line_number=1,
                severity=Severity.SUGGESTION,
                category="quality",
                comment="Tech debt",
                confidence=0.9,
            ),
            Finding(
                file_path="test.py",
                line_number=5,
                severity=Severity.SUGGESTION,
                category="quality",
                comment="More tech debt",
                confidence=0.9,
            ),
        ]
        
        issue = executor._create_tech_debt_issue(tech_debt)
        
        assert "tech-debt" in issue.title
        assert "123" in issue.title
        assert "tech-debt" in issue.labels

    def test_requests_security_review_for_blocking(self):
        executor = GitHubActionsExecutor("owner", "repo", 123)
        
        reviewers = executor._request_security_review()
        
        assert len(reviewers) > 0


class TestExecuteReviewActions:
    def test_full_action_execution(self):
        scoring = PRScoring(
            risk_score=0.85,
            complexity="high",
            requires_human_review=True,
            blocking=True,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=["Fix blocking issues"],
            summary=""
        )
        
        critical = [
            Finding(
                file_path="auth.py",
                line_number=10,
                severity=Severity.CRITICAL,
                category="security",
                comment="SQL injection",
                confidence=0.9,
            )
        ]
        
        result = execute_review_actions(
            scoring=scoring,
            findings=critical,
            repo_owner="owner",
            repo_name="repo",
            pr_number=123,
        )
        
        assert isinstance(result, ActionResult)
        assert result.check_run is not None
        assert result.check_run.conclusion == CheckConclusion.FAILURE
        assert "high-risk" in result.labels_added

    def test_empty_findings_clean_pr(self):
        scoring = PRScoring(
            risk_score=0.1,
            complexity="low",
            requires_human_review=False,
            blocking=False,
            factors=[],
            impact_analysis=None,
            affected_files=[],
            recommendations=[],
            summary=""
        )
        
        result = execute_review_actions(
            scoring=scoring,
            findings=[],
            repo_owner="owner",
            repo_name="repo",
            pr_number=123,
        )
        
        assert result.check_run.conclusion == CheckConclusion.SUCCESS


class TestActionResult:
    def test_action_result_dataclass(self):
        from src.infrastructure.services.github_actions import CheckRunResult
        
        check = CheckRunResult(
            name="test",
            status="completed",
            conclusion=CheckConclusion.SUCCESS,
            title="Test",
            summary="Summary",
            details="Details"
        )
        
        result = ActionResult(
            check_run=check,
            labels_added=["label1"],
            reviewers_assigned=["user1"],
            issues_created=["Issue #1"]
        )
        
        assert result.check_run.conclusion == CheckConclusion.SUCCESS
        assert "label1" in result.labels_added
        assert "user1" in result.reviewers_assigned
        assert "Issue #1" in result.issues_created

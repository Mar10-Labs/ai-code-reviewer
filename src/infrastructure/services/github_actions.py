from dataclasses import dataclass
from typing import Optional
from enum import Enum

from src.infrastructure.services.pr_scorer import PRScoring
from src.infrastructure.services.comment_publisher import Finding, Severity


class CheckConclusion(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ACTION_REQUIRED = "action_required"
    WARNING = "neutral"


class GitHubActionType(Enum):
    CHECK_RUN = "check_run"
    LABEL = "label"
    REVIEWER = "reviewer"
    ISSUE = "issue"


@dataclass
class CheckRunResult:
    name: str
    status: str
    conclusion: CheckConclusion
    title: str
    summary: str
    details: str


@dataclass
class LabelAction:
    name: str
    color: str
    description: str


@dataclass
class ReviewerAssignment:
    reviewers: list[str]
    team_reviewers: list[str] = None


@dataclass
class IssueCreation:
    title: str
    body: str
    labels: list[str]
    assignees: list[str] = None


@dataclass
class ActionResult:
    check_run: Optional[CheckRunResult]
    labels_added: list[str]
    reviewers_assigned: list[str]
    issues_created: list[str]


DEFAULT_LABELS = {
    "security-review": ("ff0000", "Contiene issues de seguridad"),
    "high-risk": ("ff6600", "PR de alto riesgo"),
    "tech-debt": ("9933ff", "Contiene deuda técnica"),
    "ai-reviewed": ("00ff00", "Revisado por AI Code Reviewer"),
}


class GitHubActionsExecutor:
    def __init__(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        github_client=None,
    ):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.github = github_client

    def execute_actions(
        self,
        scoring: PRScoring,
        critical_findings: list[Finding],
        warnings: list[Finding],
        tech_debt_findings: list[Finding],
        labels_config: dict = None,
    ) -> ActionResult:
        labels_added = []
        reviewers_assigned = []
        issues_created = []
        check_result = None

        check_result = self._create_check_run(scoring, critical_findings, warnings)
        
        if scoring.risk_score > 0.5:
            new_labels = self._add_risk_labels(scoring, labels_config)
            labels_added.extend(new_labels)

        for finding in critical_findings[:3]:
            if finding.category == "security":
                labels_added.append("security-review")
            if scoring.risk_score > 0.75:
                labels_added.append("high-risk")

        if tech_debt_findings:
            labels_added.append("tech-debt")
            issue = self._create_tech_debt_issue(tech_debt_findings)
            issues_created.append(issue.title)

        if scoring.blocking and critical_findings:
            reviewers = self._request_security_review()
            reviewers_assigned.extend(reviewers)

        return ActionResult(
            check_run=check_result,
            labels_added=list(set(labels_added)),
            reviewers_assigned=reviewers_assigned,
            issues_created=issues_created,
        )

    def _create_check_run(
        self,
        scoring: PRScoring,
        critical: list[Finding],
        warnings: list[Finding],
    ) -> CheckRunResult:
        if scoring.blocking:
            conclusion = CheckConclusion.FAILURE
            title = "AI Review: Blocking issues found"
        elif critical:
            conclusion = CheckConclusion.ACTION_REQUIRED
            title = "AI Review: Action required"
        elif warnings:
            conclusion = CheckConclusion.WARNING
            title = "AI Review: Warnings found"
        else:
            conclusion = CheckConclusion.SUCCESS
            title = "AI Review: Passed"

        summary_parts = [
            f"Risk Score: {scoring.risk_score:.2f} ({scoring.complexity})",
            f"Critical: {len(critical)}",
            f"Warnings: {len(warnings)}",
        ]
        if scoring.blocking:
            summary_parts.append("⚠️ BLOCKING - Requires review before merge")

        summary = "\n".join(summary_parts)
        details = "\n\n".join(scoring.recommendations)

        return CheckRunResult(
            name="ai-code-reviewer",
            status="completed",
            conclusion=conclusion,
            title=title,
            summary=summary,
            details=details,
        )

    def _add_risk_labels(
        self,
        scoring: PRScoring,
        config: dict = None,
    ) -> list[str]:
        labels = []
        
        if scoring.risk_score > 0.75:
            labels.append("high-risk")
        
        if scoring.complexity == "high":
            labels.append("complex")
        
        return labels

    def _request_security_review(self) -> list[str]:
        return ["security-team"]

    def _create_tech_debt_issue(
        self,
        findings: list[Finding],
    ) -> IssueCreation:
        grouped = {}
        for f in findings:
            if f.category not in grouped:
                grouped[f.category] = []
            grouped[f.category].append(f)

        body_parts = [
            f"## Tech Debt encontrados en PR #{self.pr_number}\n",
        ]
        
        for category, cat_findings in grouped.items():
            body_parts.append(f"### {category.title()} ({len(cat_findings)} issues)")
            for f in cat_findings[:5]:
                body_parts.append(f"- `{f.file_path}:{f.line_number}`: {f.comment}")
            if len(cat_findings) > 5:
                body_parts.append(f"- ... y {len(cat_findings) - 5} más")

        return IssueCreation(
            title=f"[tech-debt] Resolver issues de {len(findings)} en PR #{self.pr_number}",
            body="\n".join(body_parts),
            labels=["tech-debt"],
        )

    def _should_block_pr(self, scoring: PRScoring) -> bool:
        return scoring.blocking

    def _get_severity_emoji(self, severity: Severity) -> str:
        if severity == Severity.CRITICAL:
            return "🚨"
        elif severity == Severity.WARNING:
            return "⚠️"
        return "💡"


def execute_review_actions(
    scoring: PRScoring,
    findings: list[Finding],
    repo_owner: str,
    repo_name: str,
    pr_number: int,
) -> ActionResult:
    executor = GitHubActionsExecutor(repo_owner, repo_name, pr_number)
    
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    suggestions = [f for f in findings if f.severity == Severity.SUGGESTION]
    tech_debt = [f for f in suggestions if f.category in ["debt", "quality"]]
    
    return executor.execute_actions(
        scoring=scoring,
        critical_findings=critical,
        warnings=warnings,
        tech_debt_findings=tech_debt,
    )

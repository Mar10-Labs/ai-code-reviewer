from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    SUGGESTION = "suggestion"

    @property
    def weight(self) -> float:
        weights = {
            Severity.CRITICAL: 1.0,
            Severity.WARNING: 0.6,
            Severity.SUGGESTION: 0.3,
        }
        return weights[self]


@dataclass
class Finding:
    file_path: str
    line_number: int
    severity: Severity
    category: str
    comment: str
    confidence: float
    suggested_fix: Optional[str] = None
    impact: float = 0.5

    @property
    def score(self) -> float:
        return (
            self.severity.weight * 0.5 +
            self.confidence * 0.3 +
            self.impact * 0.2
        )


@dataclass
class FindingGroup:
    file_path: str
    finding_type: str
    count: int
    representative: Finding
    summary: str


@dataclass
class PublicationResult:
    published: list[Finding]
    grouped: list[FindingGroup]
    skipped: int
    total_found: int


@dataclass
class PublicationConfig:
    max_comments_per_pr: int = 5
    max_comments_per_file: int = 2
    min_score_threshold: float = 0.4
    group_similar: bool = True
    group_threshold: float = 0.8


class CommentRanker:
    def __init__(self, config: Optional[PublicationConfig] = None):
        self.config = config or PublicationConfig()

    def rank_findings(self, findings: list[Finding]) -> list[Finding]:
        scored = [(f.score, f) for f in findings if f.score >= self.config.min_score_threshold]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored]

    def limit_per_file(self, findings: list[Finding]) -> list[Finding]:
        by_file: dict[str, list[Finding]] = {}
        for f in findings:
            if f.file_path not in by_file:
                by_file[f.file_path] = []
            by_file[f.file_path].append(f)

        limited = []
        for file_path, file_findings in by_file.items():
            limited.extend(file_findings[:self.config.max_comments_per_file])
        
        return limited

    def limit_per_pr(self, findings: list[Finding]) -> list[Finding]:
        return findings[:self.config.max_comments_per_pr]

    def group_similar(self, findings: list[Finding]) -> tuple[list[Finding], list[FindingGroup]]:
        if not self.config.group_similar:
            return findings, []

        by_file_type: dict[tuple[str, str], list[Finding]] = {}
        for f in findings:
            key = (f.file_path, f.category)
            if key not in by_file_type:
                by_file_type[key] = []
            by_file_type[key].append(f)

        unique = []
        groups = []

        for (file_path, category), group_findings in by_file_type.items():
            if len(group_findings) == 1:
                unique.append(group_findings[0])
            else:
                rep = max(group_findings, key=lambda f: f.score)
                group = FindingGroup(
                    file_path=file_path,
                    finding_type=category,
                    count=len(group_findings),
                    representative=rep,
                    summary=self._generate_group_summary(group_findings)
                )
                groups.append(group)

        return unique, groups

    def _generate_group_summary(self, findings: list[Finding]) -> str:
        if not findings:
            return ""
        
        categories = set(f.category for f in findings)
        severity = findings[0].severity
        
        lines = []
        if severity == Severity.CRITICAL:
            lines.append(f"🚨 {len(findings)} issues críticos encontrados:")
        elif severity == Severity.WARNING:
            lines.append(f"⚠️ {len(findings)} warnings encontrados:")
        else:
            lines.append(f"💡 {len(findings)} sugerencias encontradas:")
        
        lines.append(f"Categoría: {', '.join(categories)}")
        
        return "\n".join(lines)

    def rank_and_filter(self, findings: list[Finding]) -> PublicationResult:
        ranked = self.rank_findings(findings)
        
        grouped_rank, groups = self.group_similar(ranked)
        
        limited_file = self.limit_per_file(grouped_rank)
        limited_pr = self.limit_per_pr(limited_file)
        
        skipped = len(findings) - len(limited_pr) - len(groups)
        
        return PublicationResult(
            published=limited_pr,
            grouped=groups,
            skipped=skipped,
            total_found=len(findings)
        )


def publish_findings(
    findings: list[Finding],
    config: Optional[PublicationConfig] = None
) -> PublicationResult:
    ranker = CommentRanker(config)
    return ranker.rank_and_filter(findings)

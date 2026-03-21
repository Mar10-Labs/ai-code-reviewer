import pytest
from src.infrastructure.services.comment_publisher import (
    CommentRanker,
    Finding,
    Severity,
    PublicationConfig,
    PublicationResult,
    publish_findings,
)


class TestFindingScore:
    def test_critical_has_highest_weight(self):
        critical = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.CRITICAL,
            category="security",
            comment="Security issue",
            confidence=0.9,
            impact=0.8
        )
        
        assert critical.severity.weight == 1.0
        assert critical.score > 0.7

    def test_warning_has_medium_weight(self):
        warning = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.WARNING,
            category="quality",
            comment="Quality issue",
            confidence=0.9,
            impact=0.8
        )
        
        assert warning.severity.weight == 0.6

    def test_suggestion_has_lowest_weight(self):
        suggestion = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.SUGGESTION,
            category="style",
            comment="Style suggestion",
            confidence=0.9,
            impact=0.8
        )
        
        assert suggestion.severity.weight == 0.3


class TestCommentRanker:
    def test_ranks_by_score(self):
        config = PublicationConfig(min_score_threshold=0.2)
        ranker = CommentRanker(config)
        
        low_priority = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.SUGGESTION,
            category="style",
            comment="Minor",
            confidence=0.6,
            impact=0.5
        )
        
        high_priority = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.CRITICAL,
            category="security",
            comment="Critical",
            confidence=0.9,
            impact=0.9
        )
        
        ranked = ranker.rank_findings([low_priority, high_priority])
        
        assert ranked[0].severity == Severity.CRITICAL
        assert ranked[1].severity == Severity.SUGGESTION

    def test_filters_below_threshold(self):
        config = PublicationConfig(min_score_threshold=0.7)
        ranker = CommentRanker(config)
        
        low_score = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.SUGGESTION,
            category="style",
            comment="Low",
            confidence=0.3,
            impact=0.2
        )
        
        high_score = Finding(
            file_path="test.py",
            line_number=1,
            severity=Severity.CRITICAL,
            category="security",
            comment="High",
            confidence=0.9,
            impact=0.9
        )
        
        ranked = ranker.rank_findings([low_score, high_score])
        
        assert len(ranked) == 1
        assert ranked[0].severity == Severity.CRITICAL


class TestLimitPerFile:
    def test_limits_to_max_per_file(self):
        config = PublicationConfig(max_comments_per_file=2)
        ranker = CommentRanker(config)
        
        findings = [
            Finding("a.py", 1, Severity.WARNING, "q", "1", 0.9, 0.5),
            Finding("a.py", 2, Severity.WARNING, "q", "2", 0.9, 0.5),
            Finding("a.py", 3, Severity.WARNING, "q", "3", 0.9, 0.5),
            Finding("b.py", 1, Severity.WARNING, "q", "4", 0.9, 0.5),
        ]
        
        ranked = ranker.rank_findings(findings)
        limited = ranker.limit_per_file(ranked)
        
        a_file_count = sum(1 for f in limited if f.file_path == "a.py")
        assert a_file_count == 2


class TestLimitPerPR:
    def test_limits_to_max_per_pr(self):
        config = PublicationConfig(max_comments_per_pr=3)
        ranker = CommentRanker(config)
        
        findings = [
            Finding("a.py", i, Severity.WARNING, "q", f"{i}", 0.9, 0.5)
            for i in range(10)
        ]
        
        ranked = ranker.rank_findings(findings)
        limited = ranker.limit_per_pr(ranked)
        
        assert len(limited) == 3


class TestGroupSimilar:
    def test_groups_similar_findings(self):
        config = PublicationConfig(group_similar=True)
        ranker = CommentRanker(config)
        
        findings = [
            Finding("a.py", 1, Severity.WARNING, "security", "Issue 1", 0.9, 0.5),
            Finding("a.py", 5, Severity.WARNING, "security", "Issue 2", 0.9, 0.5),
            Finding("a.py", 10, Severity.WARNING, "security", "Issue 3", 0.9, 0.5),
        ]
        
        unique, groups = ranker.group_similar(findings)
        
        assert len(unique) == 0
        assert len(groups) == 1
        assert groups[0].count == 3

    def test_does_not_group_different_categories(self):
        config = PublicationConfig(group_similar=True)
        ranker = CommentRanker(config)
        
        findings = [
            Finding("a.py", 1, Severity.WARNING, "security", "Sec 1", 0.9, 0.5),
            Finding("a.py", 5, Severity.WARNING, "quality", "Qual 1", 0.9, 0.5),
        ]
        
        unique, groups = ranker.group_similar(findings)
        
        assert len(unique) == 2
        assert len(groups) == 0


class TestFullPipeline:
    def test_full_ranking_pipeline(self):
        config = PublicationConfig(
            max_comments_per_pr=3,
            max_comments_per_file=1,
            min_score_threshold=0.3,
            group_similar=True
        )
        ranker = CommentRanker(config)
        
        findings = [
            Finding("a.py", 1, Severity.SUGGESTION, "style", "S1", 0.5, 0.3),
            Finding("a.py", 2, Severity.CRITICAL, "security", "C1", 0.9, 0.9),
            Finding("a.py", 3, Severity.WARNING, "security", "W1", 0.8, 0.6),
            Finding("b.py", 1, Severity.CRITICAL, "security", "C2", 0.9, 0.9),
            Finding("b.py", 2, Severity.SUGGESTION, "style", "S2", 0.5, 0.3),
        ]
        
        result = ranker.rank_and_filter(findings)
        
        assert isinstance(result, PublicationResult)
        assert result.total_found == 5
        assert result.skipped >= 0
        assert len(result.published) <= 3
        assert len(result.published) <= len([f for f in findings if f.file_path == "a.py"])
        
        for f in result.published:
            assert f.file_path in ["a.py", "b.py"]


class TestPublishFindingsHelper:
    def test_publish_findings_convenience(self):
        findings = [
            Finding("test.py", 1, Severity.CRITICAL, "security", "Critical", 0.9, 0.9),
            Finding("test.py", 2, Severity.SUGGESTION, "style", "Minor", 0.3, 0.2),
        ]
        
        result = publish_findings(findings)
        
        assert result.total_found == 2
        assert len(result.published) >= 1
        assert result.published[0].severity == Severity.CRITICAL


class TestEdgeCases:
    def test_empty_findings(self):
        result = publish_findings([])
        
        assert result.total_found == 0
        assert len(result.published) == 0
        assert result.skipped == 0

    def test_all_low_score_filtered(self):
        config = PublicationConfig(min_score_threshold=0.9)
        
        findings = [
            Finding("test.py", 1, Severity.SUGGESTION, "style", "Minor", 0.3, 0.2),
        ]
        
        result = publish_findings(findings, config)
        
        assert result.total_found == 1
        assert len(result.published) == 0
        assert result.skipped == 1

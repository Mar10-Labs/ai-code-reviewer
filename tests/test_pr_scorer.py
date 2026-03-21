import pytest
from unittest.mock import MagicMock, patch

from src.infrastructure.services.pr_scorer import (
    PRScoreCalculator,
    score_pr,
    ScoringFactor,
    PRScoring,
)
from src.models.file_context import FileContext, EnrichedFileContext


class TestPRScoringCalculator:
    def test_score_low_risk_pr(self):
        calculator = PRScoreCalculator()
        
        diff = "+def new_helper(): pass"
        contexts = []
        
        with patch.object(calculator.git_client, 'is_file_hot', return_value=False):
            score = calculator.calculate_score(diff, contexts, [])
        
        assert score.risk_score < 0.5
        assert score.complexity in ["low", "medium"]

    def test_score_high_risk_pr(self):
        calculator = PRScoreCalculator()
        
        diff = """
-def critical_function():
-    pass
-def another_critical():
-    pass
-def third():
-    pass
"""
        critical_context = FileContext(
            file_path="src/auth.py",
            language="python",
            is_critical=True,
            is_interface_file=True
        )
        enriched = EnrichedFileContext(
            file_context=critical_context,
            breaking_change_detected=True
        )
        
        with patch.object(calculator.git_client, 'is_file_hot', return_value=True):
            score = calculator.calculate_score(diff, [enriched], ["file1.py"])
        
        assert score.risk_score >= 0.5
        assert score.complexity in ["medium", "high"]

    def test_blocking_threshold(self):
        calculator = PRScoreCalculator()
        
        diff = """
-def critical():
-    pass
-def another_critical():
-    pass
-def more():
-    pass
-def even_more():
-    pass
-def final():
-    pass
"""
        critical_context = FileContext(
            file_path="src/auth.py",
            language="python",
            is_critical=True,
            is_interface_file=True
        )
        enriched = EnrichedFileContext(
            file_context=critical_context,
            breaking_change_detected=True
        )
        
        with patch.object(calculator.git_client, 'is_file_hot', return_value=True):
            score = calculator.calculate_score(diff, [enriched], ["f1.py", "f2.py"])
        
        assert score.risk_score > 0.75 or score.requires_human_review is True

    def test_scoring_factors_present(self):
        calculator = PRScoreCalculator()
        
        score = calculator.calculate_score("+x = 1", [], [])
        
        assert len(score.factors) >= 4
        factor_names = [f.name for f in score.factors]
        assert "breaking_changes" in factor_names
        assert "critical_files" in factor_names
        assert "size" in factor_names

    def test_recommendations_generated(self):
        calculator = PRScoreCalculator()
        
        score = calculator.calculate_score("+x = 1", [], [])
        
        assert len(score.recommendations) > 0

    def test_summary_format(self):
        calculator = PRScoreCalculator()
        
        score = calculator.calculate_score("+x = 1", [], [])
        
        assert isinstance(score.summary, str)
        assert len(score.summary) > 0


class TestScoringFactors:
    def test_breaking_changes_factor(self):
        calculator = PRScoreCalculator()
        
        context = FileContext(
            file_path="test.py",
            language="python"
        )
        enriched = EnrichedFileContext(
            file_context=context,
            breaking_change_detected=True
        )
        
        with patch.object(calculator.git_client, 'is_file_hot', return_value=False):
            score = calculator.calculate_score("-def old(): pass", [enriched], [])
        
        breaking_factor = next((f for f in score.factors if f.name == "breaking_changes"), None)
        assert breaking_factor is not None
        assert breaking_factor.score > 0

    def test_critical_file_factor(self):
        calculator = PRScoreCalculator()
        
        context = FileContext(
            file_path="src/auth.py",
            language="python",
            is_critical=True
        )
        enriched = EnrichedFileContext(file_context=context)
        
        with patch.object(calculator.git_client, 'is_file_hot', return_value=False):
            score = calculator.calculate_score("+x = 1", [enriched], [])
        
        critical_factor = next((f for f in score.factors if f.name == "critical_files"), None)
        assert critical_factor is not None
        assert critical_factor.score > 0

    def test_size_factor(self):
        calculator = PRScoreCalculator()
        
        large_diff = "+a = 1\n" * 100
        score = calculator.calculate_score(large_diff, [], [])
        
        size_factor = next((f for f in score.factors if f.name == "size"), None)
        assert size_factor is not None


class TestEdgeCases:
    def test_empty_diff(self):
        calculator = PRScoreCalculator()
        
        score = calculator.calculate_score("", [], [])
        
        assert score.risk_score == 0
        assert score.blocking is False

    def test_no_context(self):
        calculator = PRScoreCalculator()
        
        score = calculator.calculate_score("+x = 1", [], [])
        
        assert isinstance(score, PRScoring)
        assert score.risk_score >= 0

    def test_threshold_constants(self):
        assert PRScoreCalculator.THRESHOLD_BLOCK == 0.75
        assert PRScoreCalculator.THRESHOLD_REVIEW == 0.5


class TestHelperFunction:
    def test_score_pr_helper(self):
        score = score_pr("+x = 1", [], [])
        assert isinstance(score, PRScoring)

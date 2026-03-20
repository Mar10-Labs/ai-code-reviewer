import pytest
import os
import tempfile
from unittest.mock import patch, AsyncMock, MagicMock

from src.infrastructure.services.db import Database
from src.models.agent_state import AgentState
from src.models.review_comment import ReviewComment


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path=path)
    yield db
    os.unlink(path)


class TestDatabaseIntegration:
    def test_database_initialization_creates_tables(self, temp_db):
        with temp_db._get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            
            assert "reviews" in table_names
            assert "review_comments" in table_names
            assert "metrics" in table_names

    def test_save_and_retrieve_review(self, temp_db):
        state = AgentState(
            pr_id=100,
            pr_title="Feature: Add user auth",
            repository="org/repo",
            status="completed"
        )
        
        review_id = temp_db.save_review(state)
        assert review_id > 0
        
        review = temp_db.get_review(review_id)
        assert review is not None
        assert review["pr_id"] == 100
        assert review["pr_title"] == "Feature: Add user auth"

    def test_save_review_with_multiple_comments(self, temp_db):
        comments = [
            ReviewComment(
                file_path="auth.py",
                line_number=10,
                severity="critical",
                category="security",
                comment="SQL injection vulnerability detected in user input.",
                confidence=0.95
            ),
            ReviewComment(
                file_path="auth.py",
                line_number=25,
                severity="warning",
                category="quality",
                comment="Function too long, consider breaking it into smaller parts.",
                confidence=0.8
            ),
            ReviewComment(
                file_path="utils.py",
                line_number=5,
                severity="suggestion",
                category="style",
                comment="Consider using f-strings instead of concatenation.",
                confidence=0.7
            )
        ]
        
        state = AgentState(
            pr_id=200,
            pr_title="Security and style improvements",
            repository="org/repo",
            status="completed",
            review_comments=comments
        )
        
        review_id = temp_db.save_review(state)
        review = temp_db.get_review(review_id)
        
        assert len(review["comments"]) == 3
        assert review["comments"][0]["severity"] == "critical"
        assert review["comments"][1]["category"] == "quality"
        assert review["comments"][2]["category"] == "style"

    def test_get_all_reviews_returns_list(self, temp_db):
        for i in range(5):
            state = AgentState(
                pr_id=300 + i,
                pr_title=f"PR {i}",
                repository="org/repo",
                status="completed"
            )
            temp_db.save_review(state)
        
        reviews = temp_db.get_all_reviews(limit=10)
        assert len(reviews) == 5

    def test_get_all_reviews_respects_limit(self, temp_db):
        for i in range(10):
            state = AgentState(
                pr_id=400 + i,
                pr_title=f"PR {i}",
                repository="org/repo",
                status="completed"
            )
            temp_db.save_review(state)
        
        reviews = temp_db.get_all_reviews(limit=3)
        assert len(reviews) == 3

    def test_save_and_retrieve_metrics(self, temp_db):
        temp_db.save_metric(
            provider="groq",
            model="llama-3.3-70b",
            tokens_used=1000,
            cost_usd=0.0,
            latency_ms=150.5,
            comments_published=5,
            comments_filtered=2
        )
        
        summary = temp_db.get_metrics_summary()
        assert summary["total_requests"] == 1
        assert summary["total_tokens"] == 1000
        assert summary["total_cost_usd"] == 0.0
        assert summary["avg_latency_ms"] == 150.5

    def test_metrics_aggregation(self, temp_db):
        temp_db.save_metric("groq", "llama", 100, 0.0, 100.0)
        temp_db.save_metric("gemini", "flash", 200, 0.001, 200.0)
        temp_db.save_metric("ollama", "local", 50, 0.0, 50.0)
        
        summary = temp_db.get_metrics_summary()
        assert summary["total_requests"] == 3
        assert summary["total_tokens"] == 350
        assert summary["total_cost_usd"] == 0.001
        assert summary["avg_latency_ms"] == pytest.approx(116.67, rel=0.1)

    def test_get_nonexistent_review(self, temp_db):
        review = temp_db.get_review(99999)
        assert review is None

    def test_empty_metrics(self, temp_db):
        summary = temp_db.get_metrics_summary()
        assert summary["total_requests"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

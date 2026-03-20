import pytest
import os
import tempfile
from datetime import datetime

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


class TestDatabase:
    def test_init_creates_tables(self, temp_db):
        with temp_db._get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            
            assert "reviews" in table_names
            assert "review_comments" in table_names
            assert "metrics" in table_names

    def test_save_review(self, temp_db):
        state = AgentState(
            pr_id=123,
            pr_title="Test PR",
            repository="owner/repo",
            status="completed"
        )
        
        review_id = temp_db.save_review(state)
        assert review_id is not None
        assert review_id > 0

    def test_get_review(self, temp_db):
        state = AgentState(
            pr_id=456,
            pr_title="Test PR 2",
            repository="owner/repo",
            status="completed"
        )
        
        review_id = temp_db.save_review(state)
        review = temp_db.get_review(review_id)
        
        assert review is not None
        assert review["pr_id"] == 456
        assert review["pr_title"] == "Test PR 2"
        assert review["status"] == "completed"

    def test_get_review_with_comments(self, temp_db):
        comment = ReviewComment(
            file_path="src/main.py",
            line_number=10,
            severity="warning",
            category="quality",
            comment="This is a valid comment with enough words here.",
            confidence=0.8
        )
        
        state = AgentState(
            pr_id=789,
            pr_title="Test PR 3",
            repository="owner/repo",
            status="completed",
            review_comments=[comment]
        )
        
        review_id = temp_db.save_review(state)
        review = temp_db.get_review(review_id)
        
        assert len(review["comments"]) == 1
        assert review["comments"][0]["file_path"] == "src/main.py"
        assert review["comments"][0]["severity"] == "warning"

    def test_get_all_reviews(self, temp_db):
        for i in range(3):
            state = AgentState(
                pr_id=100 + i,
                pr_title=f"PR {i}",
                repository="owner/repo",
                status="completed"
            )
            temp_db.save_review(state)
        
        reviews = temp_db.get_all_reviews()
        assert len(reviews) == 3

    def test_save_metric(self, temp_db):
        temp_db.save_metric(
            provider="gemini",
            model="gemini-1.5-flash",
            tokens_used=500,
            cost_usd=0.001,
            latency_ms=150.5,
            comments_published=5,
            comments_filtered=2
        )
        
        summary = temp_db.get_metrics_summary()
        assert summary["total_requests"] == 1
        assert summary["total_tokens"] == 500
        assert summary["total_cost_usd"] == 0.001

    def test_get_metrics_summary(self, temp_db):
        temp_db.save_metric("gemini", "flash", 100, 0.01, 100.0)
        temp_db.save_metric("groq", "llama", 200, 0.00, 50.0)
        
        summary = temp_db.get_metrics_summary()
        assert summary["total_requests"] == 2
        assert summary["total_tokens"] == 300
        assert summary["total_cost_usd"] == 0.01

    def test_multiple_reviews_same_pr(self, temp_db):
        state = AgentState(
            pr_id=999,
            pr_title="Same PR",
            repository="owner/repo",
            status="completed"
        )
        
        id1 = temp_db.save_review(state)
        id2 = temp_db.save_review(state)
        
        assert id1 != id2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

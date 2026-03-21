import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from src.models.agent_state import AgentState, ReviewComment


COST_PER_1K_TOKENS = {
    "groq/llama-3.3-70b-versatile": 0.0007,
    "gemini/gemini-1.5-flash": 0.000075,
    "openai/gpt-4o-mini": 0.00015,
    "anthropic/claude-3-haiku-20240307": 0.00025,
}


def calculate_cost(model: str, tokens: int) -> float:
    price = COST_PER_1K_TOKENS.get(model, 0.0001)
    return round((tokens / 1000) * price, 6)


class Database:
    def __init__(self, db_path: str = "data/reviews.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_id INTEGER NOT NULL,
                    pr_title TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    comment_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS review_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    suggested_fix TEXT,
                    confidence REAL NOT NULL,
                    agent_name TEXT,
                    FOREIGN KEY (review_id) REFERENCES reviews(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_used INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0,
                    latency_ms REAL DEFAULT 0,
                    comments_published INTEGER DEFAULT 0,
                    comments_filtered INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_review(self, state: AgentState) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO reviews (pr_id, pr_title, repository, status, created_at, updated_at, comment_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                state.pr_id,
                state.pr_title,
                state.repository,
                state.status,
                state.created_at.isoformat(),
                state.updated_at.isoformat(),
                len(state.review_comments)
            ))
            review_id = cursor.lastrowid

            for comment in state.review_comments:
                conn.execute("""
                    INSERT INTO review_comments 
                    (review_id, file_path, line_number, severity, category, comment, suggested_fix, confidence, agent_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    review_id,
                    comment.file_path,
                    comment.line_number,
                    comment.severity,
                    comment.category,
                    comment.comment,
                    comment.suggested_fix,
                    comment.confidence,
                    comment.agent_name
                ))
            
            conn.commit()
            return review_id

    def get_review(self, review_id: int) -> Optional[dict]:
        with self._get_connection() as conn:
            review = conn.execute(
                "SELECT * FROM reviews WHERE id = ?", (review_id,)
            ).fetchone()
            if review:
                comments = conn.execute(
                    "SELECT * FROM review_comments WHERE review_id = ?", (review_id,)
                ).fetchall()
                return {
                    **dict(review),
                    "comments": [dict(c) for c in comments]
                }
            return None

    def get_all_reviews(self, limit: int = 100) -> list[dict]:
        with self._get_connection() as conn:
            reviews = conn.execute(
                "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in reviews]

    def save_metric(
        self,
        provider: str,
        model: str,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        comments_published: int = 0,
        comments_filtered: int = 0
    ):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO metrics 
                (timestamp, provider, model, tokens_used, cost_usd, latency_ms, comments_published, comments_filtered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                provider,
                model,
                tokens_used,
                cost_usd,
                latency_ms,
                comments_published,
                comments_filtered
            ))
            conn.commit()

    def get_metrics_summary(self) -> dict:
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) as count FROM metrics").fetchone()
            total_tokens = conn.execute("SELECT SUM(tokens_used) as total FROM metrics").fetchone()
            total_cost = conn.execute("SELECT SUM(cost_usd) as total FROM metrics").fetchone()
            avg_latency = conn.execute("SELECT AVG(latency_ms) as avg FROM metrics").fetchone()
            
            return {
                "total_requests": total["count"] or 0,
                "total_tokens": total_tokens["total"] or 0,
                "total_cost_usd": round(total_cost["total"] or 0.0, 6),
                "avg_latency_ms": round(avg_latency["avg"] or 0.0, 2)
            }

    def get_cost_by_repo(self) -> dict:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT r.repository, SUM(m.cost_usd) as cost, COUNT(*) as requests
                FROM metrics m
                JOIN reviews r ON m.review_id = r.id
                GROUP BY r.repository
                ORDER BY cost DESC
            """).fetchall()
            return [{"repo": r["repository"], "cost": round(r["cost"] or 0, 6), "requests": r["requests"]} for r in rows]


db = Database()

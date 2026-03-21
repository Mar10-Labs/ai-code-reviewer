from typing import Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

import sqlite3
from pathlib import Path


class EventStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    PULL_REQUEST = "pull_request"
    PUSH = "push"
    COMMENT = "comment"


class ReviewEvent(BaseModel):
    delivery_id: str = Field(..., description="GitHub delivery ID for idempotency")
    event_type: EventType
    repository: str
    pr_number: Optional[int] = None
    diff_content: str
    status: EventStatus = EventStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    retry_count: int = 0

    class Config:
        use_enum_values = True


class EventStore:
    def __init__(self, db_path: str = "data/events.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    delivery_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    pr_number INTEGER,
                    diff_content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    processed_at TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_status 
                ON events(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_repository 
                ON events(repository)
            """)

    def exists(self, delivery_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM events WHERE delivery_id = ?",
                (delivery_id,)
            )
            return cursor.fetchone() is not None

    def save(self, event: ReviewEvent) -> bool:
        if self.exists(event.delivery_id):
            return False

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO events (
                    delivery_id, event_type, repository, pr_number,
                    diff_content, status, error_message, created_at,
                    processed_at, retry_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.delivery_id,
                event.event_type.value if isinstance(event.event_type, Enum) else event.event_type,
                event.repository,
                event.pr_number,
                event.diff_content,
                event.status.value if isinstance(event.status, Enum) else event.status,
                event.error_message,
                event.created_at.isoformat(),
                event.processed_at.isoformat() if event.processed_at else None,
                event.retry_count
            ))
        return True

    def get_pending(self, limit: int = 10) -> list[ReviewEvent]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM events 
                WHERE status IN ('pending', 'failed') AND retry_count < 3
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

        events = []
        for row in rows:
            events.append(ReviewEvent(
                delivery_id=row['delivery_id'],
                event_type=row['event_type'],
                repository=row['repository'],
                pr_number=row['pr_number'],
                diff_content=row['diff_content'],
                status=row['status'],
                error_message=row['error_message'],
                created_at=datetime.fromisoformat(row['created_at']),
                processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                retry_count=row['retry_count']
            ))
        return events

    def update_status(
        self, 
        delivery_id: str, 
        status: EventStatus,
        error_message: Optional[str] = None
    ):
        processed_at = datetime.now(timezone.utc).isoformat() if status in [EventStatus.COMPLETED, EventStatus.FAILED] else None
        retry_inc = 1 if status == EventStatus.FAILED else 0
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE events 
                SET status = ?, 
                    error_message = ?,
                    processed_at = COALESCE(?, processed_at),
                    retry_count = retry_count + ?
                WHERE delivery_id = ?
            """, (
                status.value if isinstance(status, Enum) else status,
                error_message,
                processed_at,
                retry_inc,
                delivery_id
            ))

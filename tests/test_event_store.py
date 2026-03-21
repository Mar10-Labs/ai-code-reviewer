import pytest
import time
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.infrastructure.queue.event_store import (
    EventStore,
    EventStatus,
    EventType,
    ReviewEvent,
    IdempotencyConfig,
)


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def event_store(temp_db):
    return EventStore(db_path=temp_db, idempotency_config=IdempotencyConfig(auto_cleanup=False))


@pytest.fixture
def sample_event():
    return ReviewEvent(
        delivery_id="delivery-123",
        event_type=EventType.PULL_REQUEST,
        repository="owner/repo",
        pr_number=42,
        diff_content="diff content here"
    )


class TestEventStoreIdempotency:
    def test_exists_returns_false_for_new_event(self, event_store):
        assert event_store.exists("new-delivery-id") is False

    def test_exists_returns_true_after_save(self, event_store, sample_event):
        event_store.save(sample_event)
        assert event_store.exists("delivery-123") is True

    def test_save_returns_false_for_duplicate(self, event_store, sample_event):
        assert event_store.save(sample_event) is True
        assert event_store.save(sample_event) is False

    def test_exists_check(self, event_store, sample_event):
        assert event_store.exists("new-id") is False
        event_store.save(sample_event)
        assert event_store.exists("delivery-123") is True

    def test_get_by_idempotency_key_not_found(self, event_store):
        result = event_store.get_by_idempotency_key("non-existent-key")
        assert result is None

    def test_get_by_idempotency_key_found(self, event_store, sample_event):
        event_store.save(sample_event, idempotency_key="idem-key-123")
        result = event_store.get_by_idempotency_key("idem-key-123")
        assert result is not None
        assert result.delivery_id == "delivery-123"

    def test_deduplicate_returns_none_for_new_key(self, event_store):
        result = event_store.deduplicate("new-key", "owner/repo", 42)
        assert result is None

    def test_deduplicate_returns_existing_event(self, event_store, sample_event):
        event_store.save(sample_event, idempotency_key="dedup-key")
        result = event_store.deduplicate("dedup-key", "owner/repo", 42)
        assert result is not None
        assert result.delivery_id == "delivery-123"

    def test_multiple_events_same_idempotency_key(self, event_store):
        event1 = ReviewEvent(
            delivery_id="delivery-1",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=42,
            diff_content="diff 1"
        )
        event2 = ReviewEvent(
            delivery_id="delivery-2",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=42,
            diff_content="diff 2"
        )
        event_store.save(event1, idempotency_key="same-key")
        event_store.save(event2, idempotency_key="same-key")
        result = event_store.deduplicate("same-key", "owner/repo", 42)
        assert result.delivery_id == "delivery-2"


class TestEventStoreCleanup:
    def test_cleanup_old_events(self, temp_db):
        config = IdempotencyConfig(auto_cleanup=False)
        store = EventStore(db_path=temp_db, idempotency_config=config)

        old_event = ReviewEvent(
            delivery_id="old-delivery",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="old diff",
        )
        old_event.created_at = datetime.now(timezone.utc) - timedelta(days=10)
        store.save(old_event)

        new_event = ReviewEvent(
            delivery_id="new-delivery",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=2,
            diff_content="new diff"
        )
        store.save(new_event)

        deleted = store.cleanup_old_events(ttl_days=7)
        assert deleted >= 1
        assert store.exists("new-delivery") is True

    def test_cleanup_with_custom_ttl(self, temp_db):
        store = EventStore(db_path=temp_db, idempotency_config=IdempotencyConfig(auto_cleanup=False))

        event = ReviewEvent(
            delivery_id="test-delivery",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="test diff"
        )
        event.created_at = datetime.now(timezone.utc) - timedelta(days=5)
        store.save(event)

        deleted = store.cleanup_old_events(ttl_days=7)
        assert deleted == 0
        assert store.exists("test-delivery") is True

        deleted = store.cleanup_old_events(ttl_days=3)
        assert deleted >= 1
        assert store.exists("test-delivery") is False


class TestIdempotencyConfig:
    def test_default_config(self):
        config = IdempotencyConfig()
        assert config.ttl_days == 7
        assert config.cleanup_interval_hours == 24
        assert config.auto_cleanup is True

    def test_custom_config(self):
        config = IdempotencyConfig(ttl_days=30, cleanup_interval_hours=1, auto_cleanup=False)
        assert config.ttl_days == 30
        assert config.cleanup_interval_hours == 1
        assert config.auto_cleanup is False


class TestEventStoreIntegration:
    def test_full_idempotency_flow(self, temp_db):
        store = EventStore(db_path=temp_db, idempotency_config=IdempotencyConfig(auto_cleanup=False))

        event = ReviewEvent(
            delivery_id="unique-delivery",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=100,
            diff_content="original diff"
        )

        first_save = store.save(event, idempotency_key="pr-100")
        assert first_save is True

        duplicate_save = store.save(event, idempotency_key="pr-100")
        assert duplicate_save is False

        retrieved = store.deduplicate("pr-100", "owner/repo", 100)
        assert retrieved is not None
        assert retrieved.diff_content == "original diff"

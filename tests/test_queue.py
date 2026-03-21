import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.queue.event_store import EventStore, ReviewEvent, EventStatus, EventType
from src.infrastructure.queue.queue_manager import QueueManager, QueueConfig


@pytest.fixture
def temp_db(tmp_path):
    return str(tmp_path / "test_events.db")


@pytest.fixture
def event_store(temp_db):
    return EventStore(db_path=temp_db)


@pytest.fixture
def queue_manager(event_store):
    return QueueManager(event_store=event_store)


class TestEventStore:
    def test_save_new_event(self, event_store):
        event = ReviewEvent(
            delivery_id="test-123",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        result = event_store.save(event)
        assert result is True

    def test_save_duplicate_event(self, event_store):
        event = ReviewEvent(
            delivery_id="test-456",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        event_store.save(event)
        result = event_store.save(event)
        assert result is False

    def test_exists(self, event_store):
        event = ReviewEvent(
            delivery_id="test-789",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        event_store.save(event)
        assert event_store.exists("test-789") is True
        assert event_store.exists("non-existent") is False

    def test_update_status(self, event_store):
        event = ReviewEvent(
            delivery_id="test-update",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        event_store.save(event)
        event_store.update_status("test-update", EventStatus.PROCESSING)
        event_store.update_status("test-update", EventStatus.COMPLETED)
        
        pending = event_store.get_pending()
        ids = [e.delivery_id for e in pending]
        assert "test-update" not in ids

    def test_get_pending(self, event_store):
        for i in range(3):
            event = ReviewEvent(
                delivery_id=f"pending-{i}",
                event_type=EventType.PULL_REQUEST,
                repository="owner/repo",
                pr_number=i,
                diff_content=f"+ code {i}"
            )
            event_store.save(event)
        
        pending = event_store.get_pending()
        assert len(pending) == 3


class TestQueueManager:
    @pytest.mark.asyncio
    async def test_enqueue_new_event(self, queue_manager):
        event = ReviewEvent(
            delivery_id="queue-test-1",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        result = await queue_manager.enqueue(event)
        assert result is True
        assert queue_manager.queue_size == 1

    @pytest.mark.asyncio
    async def test_enqueue_duplicate_event(self, queue_manager):
        event = ReviewEvent(
            delivery_id="queue-test-2",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        await queue_manager.enqueue(event)
        result = await queue_manager.enqueue(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_is_duplicate(self, queue_manager):
        event = ReviewEvent(
            delivery_id="duplicate-check",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )
        await queue_manager.enqueue(event)
        assert queue_manager.is_duplicate("duplicate-check") is True
        assert queue_manager.is_duplicate("non-existent") is False

    @pytest.mark.asyncio
    async def test_worker_processes_event(self, queue_manager):
        processed = []

        async def mock_handler(event: ReviewEvent):
            processed.append(event.delivery_id)

        event = ReviewEvent(
            delivery_id="worker-test",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )

        await queue_manager.enqueue(event)
        await queue_manager.start_worker(mock_handler)
        await asyncio.sleep(0.5)
        await queue_manager.stop_worker()

        assert "worker-test" in processed

    @pytest.mark.asyncio
    async def test_worker_handles_error(self, queue_manager):
        async def failing_handler(event: ReviewEvent):
            if event.delivery_id == "fail-test":
                raise ValueError("Test error")

        event = ReviewEvent(
            delivery_id="fail-test",
            event_type=EventType.PULL_REQUEST,
            repository="owner/repo",
            pr_number=1,
            diff_content="+ new code"
        )

        await queue_manager.enqueue(event)
        await queue_manager.start_worker(failing_handler)
        await asyncio.sleep(0.5)
        await queue_manager.stop_worker()

        pending = queue_manager.event_store.get_pending()
        assert any(e.delivery_id == "fail-test" for e in pending)

import asyncio
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, field
import time

from src.infrastructure.queue.event_store import EventStore, ReviewEvent, EventStatus


@dataclass
class QueueConfig:
    max_retries: int = 3
    base_retry_delay: float = 1.0
    max_retry_delay: float = 60.0
    batch_size: int = 5


class QueueLock:
    def __init__(self):
        self._locks: dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str) -> asyncio.Lock:
        async with self._lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def release(self, key: str):
        pass

    async def is_locked(self, key: str) -> bool:
        async with self._lock:
            if key not in self._locks:
                return False
            lock = self._locks[key]
            if lock.locked():
                return True
            return False


class QueueManager:
    def __init__(
        self,
        event_store: Optional[EventStore] = None,
        config: Optional[QueueConfig] = None
    ):
        self.event_store = event_store or EventStore()
        self.config = config or QueueConfig()
        self._queue: asyncio.Queue[ReviewEvent] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._handler: Optional[Callable[[ReviewEvent], Awaitable[None]]] = None
        self._is_running = False
        self._lock = QueueLock()

    async def enqueue(self, event: ReviewEvent) -> bool:
        saved = self.event_store.save(event)
        if saved:
            await self._queue.put(event)
            return True
        return False

    def is_duplicate(self, delivery_id: str) -> bool:
        return self.event_store.exists(delivery_id)

    async def is_pr_locked(self, repository: str, pr_number: int) -> bool:
        lock_key = f"{repository}:{pr_number}"
        return await self._lock.is_locked(lock_key)

    async def acquire_pr_lock(self, event: ReviewEvent) -> Optional[asyncio.Lock]:
        if event.pr_number is None:
            return None
        lock_key = f"{event.repository}:{event.pr_number}"
        return await self._lock.acquire(lock_key)

    async def start_worker(
        self, 
        handler: Callable[[ReviewEvent], Awaitable[None]]
    ):
        self._handler = handler
        self._is_running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop_worker(self):
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def _process_queue(self):
        while self._is_running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                await self._process_event_with_retry(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Worker error: {e}")

    async def _process_event_with_retry(self, event: ReviewEvent):
        lock = await self.acquire_pr_lock(event)
        if lock and lock.locked():
            await self._queue.put(event)
            return

        if lock:
            async with lock:
                await self._process_event(event)
        else:
            await self._process_event(event)

    async def _process_event(self, event: ReviewEvent):
        self.event_store.update_status(
            event.delivery_id, 
            EventStatus.PROCESSING
        )

        try:
            if self._handler:
                await self._handler(event)

            self.event_store.update_status(
                event.delivery_id,
                EventStatus.COMPLETED
            )

        except Exception as e:
            await self._handle_failure(event, e)

    async def _handle_failure(self, event: ReviewEvent, error: Exception):
        self.event_store.update_status(
            event.delivery_id,
            EventStatus.FAILED,
            error_message=str(error)
        )

        if event.retry_count < self.config.max_retries:
            delay = self._calculate_backoff_delay(event.retry_count)
            asyncio.create_task(self._schedule_retry(event, delay))

    def _calculate_backoff_delay(self, retry_count: int) -> float:
        delay = self.config.base_retry_delay * (2 ** retry_count)
        return min(delay, self.config.max_retry_delay)

    async def _schedule_retry(self, event: ReviewEvent, delay: float):
        await asyncio.sleep(delay)
        event.retry_count += 1
        await self._queue.put(event)

    async def process_pending(self):
        pending_events = self.event_store.get_pending(self.config.batch_size)
        for event in pending_events:
            await self._process_event(event)

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_worker_running(self) -> bool:
        return self._is_running

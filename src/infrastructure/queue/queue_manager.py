import asyncio
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

from src.infrastructure.queue.event_store import EventStore, ReviewEvent, EventStatus


@dataclass
class QueueConfig:
    max_retries: int = 3
    retry_delay: float = 5.0
    batch_size: int = 5


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

    async def enqueue(self, event: ReviewEvent) -> bool:
        saved = self.event_store.save(event)
        if saved:
            await self._queue.put(event)
            return True
        return False

    def is_duplicate(self, delivery_id: str) -> bool:
        return self.event_store.exists(delivery_id)

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
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Worker error: {e}")

    async def _process_event(self, event: ReviewEvent):
        try:
            self.event_store.update_status(
                event.delivery_id, 
                EventStatus.PROCESSING
            )

            if self._handler:
                await self._handler(event)

            self.event_store.update_status(
                event.delivery_id,
                EventStatus.COMPLETED
            )

        except Exception as e:
            self.event_store.update_status(
                event.delivery_id,
                EventStatus.FAILED,
                error_message=str(e)
            )

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
